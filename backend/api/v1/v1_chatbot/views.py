import logging
import uuid
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ChatRequestSerializer, ChatResponseSerializer
from .utils import clean_citation_sources, get_page_context

logger = logging.getLogger(__name__)


DEFAULT_INSTRUCTIONS = (
    "You are Mira, the intelligent support assistant for Akvo MIS.\n"
    "Your role is to help users navigate the platform, design forms, "
    "manage data, configure approvals, and understand features.\n\n"
    "Guidelines:\n"
    "1. Ground your answers directly in the attached documentation.\n"
    "2. If the user message includes a page context tag "
    "(e.g. [Context: User is on the 'Control Center' page]), use that "
    "context when the question relates to the current page. If the question "
    "is about a general or external feature (such as downloading the mobile "
    "app, which is done via the /app server URL and not within the web "
    "Control Center), answer accurately from the documentation without "
    "forcing the answer into the current page context.\n"
    "3. Keep answers concise, step-by-step, actionable, and formatted.\n"
    "4. If docs do not cover a topic, politely inform the user.\n"
    "5. SCOPE: You only answer questions about Akvo MIS and its features "
    "(forms, data collection, approvals, users, mobile app, reports, and "
    "related platform topics). If a question is clearly unrelated to "
    "Akvo MIS — for example about politics, geography, science, history, "
    "other software products, or general knowledge — politely decline and "
    "redirect: 'I can only help with Akvo MIS questions. Feel free to ask "
    "me about forms, data collection, approvals, or any other platform "
    "feature!'\n"
)

FALLBACK_INSTRUCTIONS = (
    DEFAULT_INSTRUCTIONS
    + "\nNotice: You are operating in direct mode without active vector "
    "file search. Answer general Akvo MIS workflow questions to the best of "
    "your knowledge, but if you are uncertain about a specific configuration, "
    "prop, or schema detail, explicitly acknowledge uncertainty and advise "
    "the user to consult the Akvo MIS platform documentation or their "
    "system administrator.\n"
)


class ChatMessageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChatRequestSerializer,
        responses={
            200: ChatResponseSerializer,
            400: OpenApiResponse(description="Validation Error"),
            401: OpenApiResponse(description="Authentication Required"),
            500: OpenApiResponse(description="AI Service Error"),
        },
        description="Send message to AI Chatbot assistant.",
    )
    def post(self, request, *args, **kwargs):
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_message = serializer.validated_data["message"]
        page_url = serializer.validated_data.get("page_url", "/")
        thread_id = serializer.validated_data.get("thread_id")

        context_label = get_page_context(page_url)
        augmented_message = (
            f"[Context: User is on the '{context_label}' page]\n\n"
            f"{user_message}"
        )

        api_key = getattr(settings, "OPENAI_API_KEY", "")
        assistant_id = getattr(settings, "OPENAI_ASSISTANT_ID", "")
        vector_store_id = getattr(settings, "OPENAI_VECTOR_STORE_ID", "")

        if not api_key:
            logger.warning("OPENAI_API_KEY is not configured in settings.")
            return Response(
                {
                    "response": (
                        "AI Chatbot service is currently not configured. "
                        "Please set OPENAI_API_KEY."
                    ),
                    "thread_id": thread_id or "mock_thread_id",
                },
                status=status.HTTP_200_OK,
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)

            # Strategy 1: Try OpenAI Assistants API (threads + vector store)
            try:
                if not thread_id or thread_id.startswith("chat_"):
                    thread = client.beta.threads.create()
                    thread_id = thread.id

                try:
                    client.beta.threads.messages.create(
                        thread_id=thread_id,
                        role="user",
                        content=augmented_message,
                    )
                except Exception as post_err:
                    logger.info(
                        f"Post to thread '{thread_id}' failed ({post_err}). "
                        "Creating a new thread."
                    )
                    thread = client.beta.threads.create()
                    thread_id = thread.id
                    client.beta.threads.messages.create(
                        thread_id=thread_id,
                        role="user",
                        content=augmented_message,
                    )

                run = None
                if assistant_id:
                    try:
                        run = client.beta.threads.runs.create_and_poll(
                            thread_id=thread_id,
                            assistant_id=assistant_id,
                        )
                    except Exception as asst_err:
                        logger.warning(
                            f"Failed run with assistant_id '{assistant_id}': "
                            f"{asst_err}. Falling back to direct run."
                        )
                        run = None

                if not run:
                    run_kwargs = {
                        "thread_id": thread_id,
                        "instructions": DEFAULT_INSTRUCTIONS,
                        "model": "gpt-4o-mini",
                    }
                    if vector_store_id:
                        run_kwargs["tools"] = [{"type": "file_search"}]
                        run_kwargs["tool_resources"] = {
                            "file_search": {
                                "vector_store_ids": [vector_store_id]
                            }
                        }
                    run = client.beta.threads.runs.create_and_poll(
                        **run_kwargs
                    )

                if run.status == "completed":
                    messages = client.beta.threads.messages.list(
                        thread_id=thread_id,
                        order="desc",
                        limit=10,
                    )
                    assistant_reply = ""
                    msg_list = getattr(messages, "data", messages)
                    for msg in msg_list:
                        if getattr(msg, "role", None) == "assistant":
                            content_blocks = getattr(msg, "content", []) or []
                            for block in content_blocks:
                                if hasattr(block, "text") and hasattr(
                                    block.text, "value"
                                ):
                                    assistant_reply += block.text.value
                            break

                    cleaned_reply = clean_citation_sources(assistant_reply)
                    return Response(
                        {
                            "response": (
                                cleaned_reply
                                or (
                                    "I'm sorry, I couldn't find an answer "
                                    "to that."
                                )
                            ),
                            "thread_id": thread_id,
                        },
                        status=status.HTTP_200_OK,
                    )
            except Exception as beta_err:
                logger.info(
                    f"Assistants API endpoint unavailable ({beta_err}). "
                    "Falling back to Chat Completions with instructions."
                )

            # Strategy 2: Chat Completions API fallback
            # (always works with any key)
            chat_resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": FALLBACK_INSTRUCTIONS},
                    {"role": "user", "content": augmented_message},
                ],
            )
            reply = chat_resp.choices[0].message.content or ""
            return Response(
                {
                    "response": reply,
                    "thread_id": thread_id or f"chat_{uuid.uuid4().hex[:12]}",
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception(f"Error calling OpenAI API: {e}")
            return Response(
                {
                    "response": (
                        "Sorry, the AI service is currently unavailable. "
                        "Please try again later."
                    ),
                    "thread_id": thread_id or "error_thread",
                },
                status=status.HTTP_200_OK,
            )
