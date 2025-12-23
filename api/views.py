from django.contrib.auth.models import User
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.exceptions import NotFound

from api.models import Entry, FieldDefinition, HobbyType, SavedView, Tag
from api import serializers


class HobbyTypeViewset(viewsets.ModelViewSet):
    queryset = HobbyType.objects.all()
    serializer_class = serializers.HobbyTypeSerializer

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TagViewset(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = serializers.TagSerializer

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class SavedViewViewset(viewsets.ModelViewSet):
    queryset = SavedView.objects.all()
    serializer_class = serializers.SavedViewSerializer

    def get_queryset(self):
        key = self.kwargs.get("hobby_types_pk")
        try:
            hobby_type = HobbyType.objects.get(id=key, owner=self.request.user)
        except HobbyType.DoesNotExist:
            raise NotFound("Hobby Type does not exist.")
        return self.queryset.filter(owner=self.request.user, hobby_type=hobby_type)

    def perform_create(self, serializer):
        key = self.kwargs.get("hobby_types_pk")
        try:
            hobby_type = HobbyType.objects.get(id=key, owner=self.request.user)
        except HobbyType.DoesNotExist:
            raise NotFound("Hobby Type does not exist.")
        serializer.save(owner=self.request.user, hobby_type=hobby_type)


class EntryViewset(viewsets.ModelViewSet):
    queryset = Entry.objects.all()
    serializer_class = serializers.EntrySerializer

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldDefinitionViewset(viewsets.ModelViewSet):
    queryset = FieldDefinition.objects.all()
    serializer_class = serializers.FieldDefinitionSerializer

    def get_queryset(self):
        key = self.kwargs.get("hobby_types_pk")
        try:
            hobby_type = HobbyType.objects.get(id=key, owner=self.request.user)
        except HobbyType.DoesNotExist:
            raise NotFound("Hobby Type does not exist.")
        return self.queryset.filter(hobby_type=hobby_type).order_by("order", "id")

    def perform_create(self, serializer):
        key = self.kwargs.get("hobby_types_pk")
        try:
            hobby_type = HobbyType.objects.get(id=key, owner=self.request.user)
        except HobbyType.DoesNotExist:
            raise NotFound("Hobby Type does not exist.")
        serializer.save(hobby_type=hobby_type)
