from libs.generate_text.inputs import GenerateTextPersonaInput
from tests.factories.generate_text import build_generate_text_state


def test_build_persona_groups_stored_dict_into_persona_input() -> None:
    generate_text_state = build_generate_text_state(
        persona_name="Marta Quill",
        persona_bio="Writes about slow mornings.",
        persona_background="Former baker.",
        persona_expertise="Fermentation.",
        persona_writing_style="Short punchy sentences.",
        persona_sample_writing="The starter bubbled all night.",
    )

    build_persona_result = generate_text_state.build_persona()

    assert build_persona_result == GenerateTextPersonaInput(
        name="Marta Quill",
        bio="Writes about slow mornings.",
        background="Former baker.",
        expertise="Fermentation.",
        writing_style="Short punchy sentences.",
        sample_writing="The starter bubbled all night.",
    )
