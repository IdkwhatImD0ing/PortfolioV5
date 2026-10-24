"""Who the agent speaks as, picked per call. The classic persona is the default.

Two personas exist:

- ``classic``: Bill speaking as himself (prompts.py). Every caller that does not
  ask for another persona gets it, so the old site and every existing Retell
  agent version behave exactly as before.
- ``ming-sect``: the sound-transmission of the sect (the home page), a guide that talks
  about Bill in the third person (prompts_sect.py), screened by the sect's judge
  (guardrail.sect_security_guardrail). The sect is now 日月神教, the Sun Moon
  Divine Cult; the id keeps its first name, the Ming Sect, because the client
  routes send it and calls in flight carry it.

How a caller asks for one:

- Voice: Retell's ``call_details`` message, the first one on the websocket,
  carries the call's ``metadata`` and ``retell_llm_dynamic_variables`` as the
  browser attached them at create-web-call. ``persona_from_call`` reads
  ``metadata.persona``, then ``retell_llm_dynamic_variables.persona``. The client
  route sets it for calls placed from the sect, / or /sect (client/src/app/api/create-web-call).
- Text: ``/chat`` takes an optional ``persona`` field (custom_types.TextChatRequest).

An unknown, blank or malformed value means classic: a persona is a costume, not
a permission, so nothing here can fail a call.
"""

from dataclasses import dataclass

from agents import InputGuardrail

import prompts
import prompts_sect
from guardrail import sect_security_guardrail, security_guardrail

__all__ = [
    "CLASSIC",
    "DEFAULT_PERSONA",
    "MING_SECT",
    "PERSONAS",
    "Persona",
    "get_persona",
    "persona_from_call",
]

CLASSIC = "classic"
MING_SECT = "ming-sect"
DEFAULT_PERSONA = CLASSIC


@dataclass(frozen=True)
class Persona:
    """Everything that changes with the persona. Tools and models do not."""

    key: str
    voice_system_prompt: str
    text_system_prompt: str
    # The voice call's first words (llm.LlmClient.draft_begin_message).
    begin_sentence: str
    # What the visitor gets when the guardrail trips (see llm.LlmClient).
    refusal_message: str
    interruption_message: str
    reminder_checkin_message: str
    guardrail: InputGuardrail

    def system_prompt(self, mode: str) -> str:
        """The instructions for `mode`: the voice prompt for "voice", else the text one."""
        return self.voice_system_prompt if mode == "voice" else self.text_system_prompt


PERSONAS: dict[str, Persona] = {
    CLASSIC: Persona(
        key=CLASSIC,
        voice_system_prompt=prompts.voice_system_prompt,
        text_system_prompt=prompts.text_system_prompt,
        begin_sentence=prompts.begin_sentence,
        refusal_message=prompts.guardrail_refusal_message,
        interruption_message=prompts.guardrail_interruption_message,
        reminder_checkin_message=prompts.reminder_checkin_message,
        guardrail=security_guardrail,
    ),
    MING_SECT: Persona(
        key=MING_SECT,
        voice_system_prompt=prompts_sect.sect_voice_system_prompt,
        text_system_prompt=prompts_sect.sect_text_system_prompt,
        begin_sentence=prompts_sect.sect_begin_sentence,
        refusal_message=prompts_sect.sect_guardrail_refusal_message,
        interruption_message=prompts_sect.sect_guardrail_interruption_message,
        reminder_checkin_message=prompts_sect.sect_reminder_checkin_message,
        guardrail=sect_security_guardrail,
    ),
}


def get_persona(key: object = None) -> Persona:
    """The persona named `key` (case and surrounding spaces ignored), else classic."""
    if isinstance(key, str):
        persona = PERSONAS.get(key.strip().lower())
        if persona is not None:
            return persona
    return PERSONAS[DEFAULT_PERSONA]


def persona_from_call(call: object) -> Persona:
    """The persona a Retell call asked for, from its call_details ``call`` object.

    ``metadata.persona`` is read first, then ``retell_llm_dynamic_variables.persona``;
    the first one present decides. Anything missing or unknown is classic.
    """
    if not isinstance(call, dict):
        return get_persona(None)
    for field in ("metadata", "retell_llm_dynamic_variables"):
        bag = call.get(field)
        if isinstance(bag, dict):
            requested = bag.get("persona")
            if isinstance(requested, str) and requested.strip():
                return get_persona(requested)
    return get_persona(None)
