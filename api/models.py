# models.py
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class HobbyType(models.Model):
    """
    A user-defined "collection"/type, e.g. Movies, Gym, Guitar Practice, Projects, etc.
    This is the CMS template that owns a set of FieldDefinitions.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hobby_types",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)  # unique per owner via constraint below
    description = models.TextField(blank=True)

    # Optional presentation settings for the frontend
    icon = models.CharField(max_length=64, blank=True)
    color = models.CharField(max_length=32, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "slug"],
                name="uniq_hobbytype_owner_slug",
            ),
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="uniq_hobbytype_owner_name",
            ),
        ]
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name}"


class FieldDefinition(models.Model):
    """
    Defines a field for a given HobbyType (like a CMS schema).
    Values for these fields are stored in Entry.data (JSON).
    """

    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        LONG_TEXT = "long_text", "Long text"
        NUMBER = "number", "Number"
        BOOLEAN = "boolean", "Boolean"
        DATE = "date", "Date"
        DATETIME = "datetime", "Date & time"
        SELECT = "select", "Select"
        MULTI_SELECT = "multi_select", "Multi-select"
        URL = "url", "URL"
        LIST = "list", "List"

    hobby_type = models.ForeignKey(
        HobbyType,
        on_delete=models.CASCADE,
        related_name="fields",
    )

    # Used as the JSON key in Entry.data
    key = models.SlugField(max_length=64)
    label = models.CharField(max_length=120)
    help_text = models.CharField(max_length=240, blank=True)

    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    required = models.BooleanField(default=False)

    # For select options, numeric ranges, etc. Example:
    # {"choices": ["to_watch","watching","watched"], "min": 0, "max": 10, "step": 0.5}
    options = models.JSONField(default=dict, blank=True)

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hobby_type", "key"],
                name="uniq_fielddef_type_key",
            ),
        ]
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.hobby_type.name}: {self.label} ({self.key})"


class Tag(models.Model):
    """
    Simple per-owner tags so you can reuse tags across types/entries.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
    )
    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=72)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "slug"], name="uniq_tag_owner_slug"
            ),
            models.UniqueConstraint(
                fields=["owner", "name"], name="uniq_tag_owner_name"
            ),
        ]
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:72]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Entry(models.Model):
    """
    An item/log inside a HobbyType (e.g. one Movie, one Gym session, one Project).
    Core metadata lives on columns; custom fields live in data (JSON).
    """

    class Status(models.TextChoices):
        BACKLOG = "backlog", "Backlog"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    hobby_type = models.ForeignKey(
        HobbyType,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    # Optional core title to make lists fast; you can also store title in data["title"]
    title = models.CharField(max_length=200, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.BACKLOG
    )

    tags = models.ManyToManyField(Tag, blank=True, related_name="entries")

    # All dynamic fields go here keyed by FieldDefinition.key
    data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "hobby_type", "status"]),
            models.Index(fields=["owner", "hobby_type", "updated_at"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.hobby_type.name}: {self.title}"

    # ---------------------------
    # Validation against schema
    # ---------------------------
    def clean(self):
        """
        Validate Entry.data against the FieldDefinitions for its HobbyType.
        Keep this lightweight; heavier validation can live in DRF serializers too.
        """
        super().clean()

        if not self.hobby_type_id:
            return

        fields = list(self.hobby_type.fields.all())
        schema = {f.label: f for f in fields}

        # Unknown keys check (optional but recommended)
        unknown = set(self.data.keys()) - set(schema.keys())
        if unknown:
            raise ValidationError({"data": f"Unknown field keys: {sorted(unknown)}"})

        # Required fields check + type checks
        errors: dict[str, str] = {}

        for f in fields:
            key = f.label
            present = key in self.data and self.data.get(key) not in (None, "", [])
            if f.required and not present:
                errors[key] = "This field is required."
                continue
            if not present:
                continue

            value = self.data.get(key)
            try:
                self._validate_value(f, value)
            except ValidationError as e:
                errors[key] = e.message

        if errors:
            print({"data": errors})

    def _validate_value(self, field: FieldDefinition, value):
        ft = field.field_type
        opts = field.options or {}

        if ft in (
            FieldDefinition.FieldType.TEXT,
            FieldDefinition.FieldType.LONG_TEXT,
            FieldDefinition.FieldType.URL,
        ):
            if not isinstance(value, str):
                raise ValidationError("Must be a string.")
            return

        if ft == FieldDefinition.FieldType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValidationError("Must be true/false.")
            return

        if ft == FieldDefinition.FieldType.NUMBER:
            if not isinstance(value, (int, float)):
                raise ValidationError("Must be a number.")
            minv = opts.get("min")
            maxv = opts.get("max")
            if minv is not None and value < minv:
                raise ValidationError(f"Must be ≥ {minv}.")
            if maxv is not None and value > maxv:
                raise ValidationError(f"Must be ≤ {maxv}.")
            return

        if ft in (FieldDefinition.FieldType.DATE, FieldDefinition.FieldType.DATETIME):
            # Store ISO strings from Next.js (recommended). Validate basic type here.
            # You can do strict parsing in your serializer if you want.
            if not isinstance(value, str):
                raise ValidationError("Must be an ISO date/datetime string.")
            return

        if ft == FieldDefinition.FieldType.SELECT:
            choices = opts.get("choices", [])
            if not isinstance(value, str):
                raise ValidationError("Must be a string.")
            if choices and value not in choices:
                raise ValidationError("Invalid choice.")
            return

        if ft == FieldDefinition.FieldType.MULTI_SELECT:
            choices = opts.get("choices", [])
            if not isinstance(value, list) or not all(
                isinstance(x, str) for x in value
            ):
                raise ValidationError("Must be a list of strings.")
            if choices and any(x not in choices for x in value):
                raise ValidationError("Contains invalid choice(s).")
            return

        if ft == FieldDefinition.FieldType.LIST:
            if not isinstance(value, list):
                raise ValidationError("Must be a list.")

            item_type = opts.get("item_type", "text")
            min_items = opts.get("min_items")
            max_items = opts.get("max_items")

            if min_items is not None and len(value) < min_items:
                raise ValidationError(f"Must contain at least {min_items} items.")

            if max_items is not None and len(value) > max_items:
                raise ValidationError(f"Must contain at most {max_items} items.")

            for item in value:
                if item_type == "text" and not isinstance(item, str):
                    raise ValidationError("All items must be strings.")
                if item_type == "number" and not isinstance(item, (int, float)):
                    raise ValidationError("All items must be numbers.")
                if item_type == "boolean" and not isinstance(item, bool):
                    raise ValidationError("All items must be booleans.")

            return

        raise ValidationError("Unsupported field type.")


class SavedView(models.Model):
    """
    Optional but very 'CMS': saved filters/sorts per HobbyType.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    hobby_type = models.ForeignKey(
        HobbyType,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )

    name = models.CharField(max_length=120)

    # Example:
    # filters = {"status": "to_watch", "rating": {"gte": 8}, "tags": ["sci-fi"]}
    filters = models.JSONField(default=dict, blank=True)

    # Example: ["-updated_at"] or ["data.rating", "-created_at"]
    sort = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "hobby_type", "name"],
                name="uniq_savedview_owner_type_name",
            ),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.hobby_type.name} / {self.name}"
