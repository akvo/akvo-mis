class QuestionTypes:
    geo = 1
    administration = 2
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

    FieldStr = {
        geo: "Geo",
        administration: "Administration",
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
