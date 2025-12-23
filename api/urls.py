from django.urls import path, include

# from rest_framework import routers
from rest_framework_nested import routers

from api import views

router = routers.DefaultRouter()
router.register("hobby-types", views.HobbyTypeViewset, basename="hobby_types")

hobby_router = routers.NestedDefaultRouter(router, r"hobby-types", lookup="hobby_types")
hobby_router.register(
    r"fields", views.FieldDefinitionViewset, basename="hobby_types_fields"
)
hobby_router.register(
    r"saved-view", views.SavedViewViewset, basename="hobby_types_savedview"
)
entry_router = routers.DefaultRouter()
entry_router.register("entries", views.EntryViewset, basename="entries")

tag_router = routers.DefaultRouter()
tag_router.register("tags", views.TagViewset, basename="tags")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(entry_router.urls)),
    path("", include(hobby_router.urls)),
    path("", include(tag_router.urls)),
]
