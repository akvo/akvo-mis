from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={"blank": "Message cannot be blank."},
    )
    page_url = serializers.CharField(
        required=False,
        allow_blank=True,
        default="/",
    )
    thread_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    thread_id = serializers.CharField()
