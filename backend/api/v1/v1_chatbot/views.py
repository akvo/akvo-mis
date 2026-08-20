import logging
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ChatRequestSerializer, ChatResponseSerializer
from .utils import get_page_context

logger = logging.getLogger(__name__)


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

            # 1. Create or reuse thread
            if not thread_id:
                thread = client.beta.threads.create()
                thread_id = thread.id

            # 2. Add message to thread
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=augmented_message,
            )

            # 3. Run assistant
            run_params = {"thread_id": thread_id}
            if assistant_id:
                run_params["assistant_id"] = assistant_id
                run = client.beta.threads.runs.create_and_poll(**run_params)
            else:
                # Fallback run with default instructions
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=thread_id,
                    instructions="You are Mira, the Akvo MIS assistant.",
                    model="gpt-4o-mini",
                )

            if run.status == "completed":
                messages = client.beta.threads.messages.list(
                    thread_id=thread_id,
                    order="desc",
                    limit=1,
                )
                assistant_reply = ""
                for msg in messages:
                    if msg.role == "assistant":
                        for block in msg.content:
                            if hasattr(block, "text") and hasattr(
                                block.text, "value"
                            ):
                                assistant_reply += block.text.value
                        break

                return Response(
                    {
                        "response": (
                            assistant_reply
                            or "I'm sorry, I couldn't find an answer to that."
                        ),
                        "thread_id": thread_id,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                logger.error(
                    f"OpenAI Assistant run failed with status: {run.status}"
                )
                return Response(
                    {
                        "response": (
                            "Sorry, I encountered an issue processing your "
                            "request. Please try again."
                        ),
                        "thread_id": thread_id,
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
