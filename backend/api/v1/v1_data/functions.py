import re
import base64
from django.conf import settings
from django.core.cache import cache
from datetime import datetime
from datetime import timedelta
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Questions
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_profile.models import Entity, EntityData
from faker import Faker

fake = Faker()


def get_cache(name):
    # Bypass cache under TEST_ENV. The production file-based cache lives at a
    # single host-level path shared across all parallel test workers, which
    # causes flaky failures when workers read stale entries written by peers.
    if getattr(settings, "TEST_ENV", False):
        return None
    name = re.sub(r"[\W_]+", "_", name)
    today = datetime.now().strftime("%Y%m%d")
    cache_name = f"{today}-{name}"
    data = cache.get(cache_name)
    if data:
        return data
    return None


def create_cache(name, resp, timeout=None):
    if getattr(settings, "TEST_ENV", False):
        return
    name = re.sub(r"[\W_]+", "_", name)
    today = datetime.now().strftime("%Y%m%d")
    cache_name = f"{today}-{name}"
    cache.set(cache_name, resp, timeout=timeout)


def set_answer_data(
    data: FormData,
    question: Questions,
    dep_values: dict = None,
):
    name = None
    value = None
    option = None

    if question.type == QuestionTypes.geo:
        option = data.geo
    elif (
        question.type == QuestionTypes.cascade
        and question.extra
        and question.extra.get("type") == "entity"
    ):
        entity, created = Entity.objects.get_or_create(
            name=question.extra.get("name")
        )
        name = None
        if entity:
            ed = (
                entity.entity_data.filter(administration=data.administration)
                .order_by("?")
                .first()
            )
            if ed:
                name = ed.name
        if not name:
            prefix = "{0}".format(
                entity.name if created else question.extra.get("name")
            )
            entity_adm = data.administration
            name = f"{prefix} {entity_adm.name}"
            EntityData.objects.get_or_create(
                entity=entity,
                name=name,
                administration=entity_adm,
            )
    elif question.type == QuestionTypes.cascade:
        name = data.administration.full_path_name.replace("|", " - ")
        value = data.administration.id
    elif (
        question.type == QuestionTypes.text or
        question.type == QuestionTypes.input
    ):
        name = fake.company() if question.meta else fake.sentence(nb_words=3)
    elif question.type == QuestionTypes.number:
        min = 1
        max = 50
        if question.rule and question.rule.get("min"):
            min = question.rule["min"]
        if question.rule and question.rule.get("max"):
            max = question.rule["max"]
        if dep_values and dep_values.get("max"):
            max = dep_values["max"]
        if dep_values and dep_values.get("min"):
            min = dep_values["min"]
        value = fake.random_int(min=min, max=max)
    elif question.type == QuestionTypes.option:
        option = [question.options.order_by("?").first().value]
        if dep_values and dep_values.get("options"):
            option = fake.random_choices(
                dep_values["options"],
                length=1
            )
    elif question.type == QuestionTypes.multiple_option:
        option = list(
            question.options.order_by("?")
            .values_list("value", flat=True)[
                0: fake.random_int(min=1, max=3)
            ]
        )
        if dep_values and dep_values.get("options"):
            option = fake.random_choices(
                dep_values["options"],
                length=fake.random_int(min=1, max=3)
            )
    elif question.type == QuestionTypes.image:
        name = fake.image_url()
    elif question.type == QuestionTypes.attachment:
        name = fake.file_name()
    elif question.type == QuestionTypes.signature:
        """Loads an image from the source/images directory and returns it as a
        base64 encoded string."""
        image_path = "./source/images/fake_signature.png"
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
            base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
            name = f"data:image/png;base64,{base64_encoded}"
    elif question.type == QuestionTypes.date:
        days = fake.random_int(min=1, max=30)
        name = (data.created + timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    else:
        pass

    return name, value, option


def add_fake_answers(data):
    form = data.form
    meta_name = []
    dep_questions = form.form_questions.filter(
        dependency__isnull=False
    ).distinct()
    dep_values = {}
    for question in dep_questions:
        if question.dependency:
            for d in question.dependency:
                dep_values[d.get("id")] = d
    questions = form.form_questions.all().order_by(
        "question_group__order", "order"
    )
    for question in questions:
        name, value, option = set_answer_data(
            data=data,
            question=question,
            dep_values=dep_values.get(question.id, None),
        )
        if question.meta:
            if name:
                meta_name.append(name)
            elif option and question.type != QuestionTypes.geo:
                meta_name.append(",".join(option))
            elif value and question.type != QuestionTypes.cascade:
                meta_name.append(str(value))
            else:
                pass

        if question.type == QuestionTypes.cascade:
            name = None

        seed = True
        if question.dependency:
            for d in question.dependency:
                prev_answer = Answers.objects.filter(
                    data=data, question_id=d.get("id")
                ).first()
                if prev_answer and prev_answer.options:
                    seed = False
                    for o in prev_answer.options:
                        if o in d.get("options", []):
                            seed = True
        if seed:
            Answers.objects.create(
                data=data,
                question=question,
                name=name,
                value=value,
                options=option,
                created_by=data.created_by,
            )
    if len(meta_name) > 0:
        name = " - ".join(meta_name)
        # make sure the name is not empty white spaces
        if len(name.strip()):
            data.name = name
    data.save()
