from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from api.models import Entry, FieldDefinition, HobbyType, Tag, SavedView

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "email", "id")


class HobbyTypeSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)

    class Meta:
        model = HobbyType
        fields = "__all__"


class TagSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)

    class Meta:
        model = Tag
        fields = "__all__"


class FieldDefinitionSerializer(serializers.ModelSerializer):
    hobby_type = serializers.PrimaryKeyRelatedField(
        queryset=HobbyType.objects.all(), many=False
    )

    class Meta:
        model = FieldDefinition
        fields = [
            "id",
            "hobby_type",  # ID only
            "key",
            "label",
            "help_text",
            "field_type",
            "required",
            "options",
            "order",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_hobby_type(self, hobby_type: HobbyType):
        request = self.context["request"]
        if hobby_type.owner_id != request.user.id:
            raise serializers.ValidationError("You do not own this hobby type.")
        return hobby_type

    def validate_key(self, key: str):
        # Keep it safe for JSON keys + frontend use
        if "-" in key:
            raise serializers.ValidationError("Use snake_case (no hyphens).")
        return key


class EntrySerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    hobby_type = serializers.PrimaryKeyRelatedField(queryset=HobbyType.objects.all())
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

    class Meta:
        model = Entry
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_hobby_type(self, hobby_type: HobbyType):
        """
        Ensure user can only create entries under their own HobbyTypes.
        """
        request = self.context["request"]
        if hobby_type.owner_id != request.user.id:
            raise serializers.ValidationError("You do not own this hobby type.")
        return hobby_type

    def validate_tags(self, tags):
        """
        Ensure tags belong to user too (if you have per-owner tags).
        """
        request = self.context["request"]
        bad = [t.id for t in tags if t.owner_id != request.user.id]
        if bad:
            raise serializers.ValidationError(f"Invalid tag ids: {bad}")
        return tags

    def validate(self, attrs):
        """
        Run the model's clean() to validate Entry.data against FieldDefinitions.
        """
        request = self.context["request"]
        tags = attrs.pop("tags", None)  # temporarily remove for model init

        entry = Entry(
            owner=request.user,
            **attrs,
        )
        try:
            entry.clean()  # calls your schema validation in models.py
        except DjangoValidationError as e:
            # Convert Django ValidationError -> DRF ValidationError
            raise serializers.ValidationError(
                e.message_dict if hasattr(e, "message_dict") else e.messages
            )

        # put tags back so create/update can handle them
        if tags is not None:
            attrs["tags"] = tags
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        tags = validated_data.pop("tags", [])

        entry = Entry.objects.create(**validated_data)
        if tags:
            entry.tags.set(tags)
        return entry

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # validate against schema on update too
        try:
            instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if hasattr(e, "message_dict") else e.messages
            )

        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance


class SavedViewSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    hobby_type = serializers.PrimaryKeyRelatedField(
        queryset=HobbyType.objects.all(), many=False
    )

    class Meta:
        model = SavedView
        fields = "__all__"
        read_only_fields = ["id", "created_at"]

    def validate_hobby_type(self, hobby_type: HobbyType):
        request = self.context["request"]
        if hobby_type.owner_id != request.user.id:
            raise serializers.ValidationError("You do not own this hobby type.")
        return hobby_type

    def validate_key(self, key: str):
        # Keep it safe for JSON keys + frontend use
        if "-" in key:
            raise serializers.ValidationError("Use snake_case (no hyphens).")
        return key
