class QuestionTypes:
    geo = 1
    text = 3
    number = 4
    option = 5
    multiple_option = 6
    cascade = 7
    image = 8
    date = 9
    autofield = 10
    attachment = 11
    signature = 12
    input = 13
    geoshape = 14
    geotrace = 15
    tree = 16
    table = 17

    FieldStr = {
        geo: "Geo",
        text: "Text",
        number: "Number",
        option: "Option",
        multiple_option: "Multiple_Option",
        cascade: "Cascade",
        image: "Image",
        date: "Date",
        autofield: "Autofield",
        attachment: "Attachment",
        signature: "Signature",
        input: "Input",
        geoshape: "Geoshape",
        geotrace: "Geotrace",
        tree: "Tree",
        table: "Table",
    }


class AttributeTypes:
    chart = 1
    aggregate = 2
    table = 3
    jmp = 4
    advanced_filter = 5

    FieldStr = {
        chart: "chart",
        aggregate: "aggregate",
        table: "table",
        jmp: "jmp",
        advanced_filter: "advanced_filter",
    }


class FormTypes:
    registration = 1
    monitoring = 2

    FieldStr = {
        registration: "Registration",
        monitoring: "Monitoring",
    }


class FormStatus:
    draft = 1
    published = 2

    FieldStr = {
        draft: "draft",
        published: "published",
    }


_CAMEL_FIELDS = {
    "displayOnly": "display_only",
    "dependencyRule": "dependency_rule",
    "shortLabel": "short_label",
    "variableName": "variable_name",
    "hiddenString": "hidden_string",
    "requiredDoubleEntry": "required_double_entry",
    "addonBefore": "addon_before",
    "addonAfter": "addon_after",
    "dataApiUrl": "data_api_url",
}

# Inverse of _CAMEL_FIELDS: snake_case -> camelCase (for export)
_SNAKE_TO_CAMEL = {v: k for k, v in _CAMEL_FIELDS.items()}

# Form Import/Export (FB-007)
FORM_IMPORT_SUPPORTED_VERSIONS = frozenset({1})

_TYPE_STR_TO_INT = {
    v.lower(): k for k, v in QuestionTypes.FieldStr.items()
}

_TYPE_INT_TO_STR = {
    k: v.lower() for k, v in QuestionTypes.FieldStr.items()
}
