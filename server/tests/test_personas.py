"""The persona switch (personas.py): classic by default, the Sun Moon Divine Cult on request.

What these pin:
- Nothing changes for a caller that doesn't ask: the classic persona is the same
  prompt, greeting, refusals and judge as before, and an old-site call (metadata
  without a persona) never rebuilds the agent.
- A call or chat that asks for "ming-sect" gets the sect's prompt, greeting,
  refusals and judge, with the same tools and the same navigation.
- The sect prompt carries the classic prompt's facts, so a fact changed in
  prompts.py fails here until prompts_sect.py is updated too.
- The sect's judge is the classic rubric plus a note, never a rewrite of it.
"""

import asyncio
import hashlib
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents import GuardrailFunctionOutput, RunContextWrapper

import guardrail
import prompts
import prompts_sect
from custom_types import ResponseRequiredRequest, Utterance
from guardrail import GuardrailVerdict
from llm import LlmClient
from personas import (
    CLASSIC,
    MING_SECT,
    PERSONAS,
    get_persona,
    persona_from_call,
)

SECT = PERSONAS[MING_SECT]
CLASSIC_PERSONA = PERSONAS[CLASSIC]

# CJK Unified Ideographs: what an English TTS voice can't read.
_CJK = re.compile(r"[㐀-鿿]")


# --- choosing a persona ------------------------------------------------------


class TestGetPersona:
    @pytest.mark.parametrize("key", [None, "", "   ", "classic", "bogus", "sect", 7, ["ming-sect"]])
    def test_anything_but_a_known_name_is_classic(self, key):
        assert get_persona(key) is CLASSIC_PERSONA

    @pytest.mark.parametrize("key", ["ming-sect", " MING-SECT ", "Ming-Sect"])
    def test_the_sect_by_name_ignoring_case_and_spaces(self, key):
        assert get_persona(key) is SECT


class TestPersonaFromCall:
    @pytest.mark.parametrize(
        "call",
        [
            None,
            "call",
            {},
            # The old site's calls: metadata, but no persona in it.
            {"agent_id": "agent_c5ae", "metadata": {"platform": "web", "events_channel": "voice-abc"}},
            {"metadata": "ming-sect"},
            {"metadata": {"persona": 1}},
            {"metadata": {"persona": "bogus"}},
            {"retell_llm_dynamic_variables": {"persona": ""}},
        ],
    )
    def test_no_usable_request_is_classic(self, call):
        assert persona_from_call(call) is CLASSIC_PERSONA

    def test_metadata_persona(self):
        assert persona_from_call({"metadata": {"persona": "ming-sect", "platform": "web"}}) is SECT

    def test_dynamic_variables_persona(self):
        assert persona_from_call({"retell_llm_dynamic_variables": {"persona": "ming-sect"}}) is SECT

    def test_metadata_is_read_first(self):
        call = {
            "metadata": {"persona": "classic"},
            "retell_llm_dynamic_variables": {"persona": "ming-sect"},
        }
        assert persona_from_call(call) is CLASSIC_PERSONA

    def test_a_blank_metadata_persona_falls_through_to_the_variables(self):
        call = {
            "metadata": {"persona": "  "},
            "retell_llm_dynamic_variables": {"persona": "ming-sect"},
        }
        assert persona_from_call(call) is SECT


# --- the classic persona is exactly what it was ------------------------------


class TestClassicIsUnchanged:
    def test_classic_holds_the_prompts_module_objects(self):
        assert CLASSIC_PERSONA.voice_system_prompt is prompts.voice_system_prompt
        assert CLASSIC_PERSONA.text_system_prompt is prompts.text_system_prompt
        assert CLASSIC_PERSONA.begin_sentence is prompts.begin_sentence
        assert CLASSIC_PERSONA.refusal_message is prompts.guardrail_refusal_message
        assert CLASSIC_PERSONA.interruption_message is prompts.guardrail_interruption_message
        assert CLASSIC_PERSONA.reminder_checkin_message is prompts.reminder_checkin_message
        assert CLASSIC_PERSONA.guardrail is guardrail.security_guardrail

    @pytest.mark.parametrize(
        "mode, prompt",
        [("voice", prompts.voice_system_prompt), ("text", prompts.text_system_prompt)],
        ids=["voice", "text"],
    )
    def test_a_client_that_asks_for_nothing_gets_the_classic_prompt(self, mode, prompt):
        client = LlmClient("t", mode=mode)
        assert client.persona is CLASSIC_PERSONA
        assert client.agent.instructions is prompt
        assert client.draft_begin_message().content == prompts.begin_sentence

    def test_an_old_site_call_keeps_the_classic_agent_object(self):
        """No rebuild for a call that didn't ask: the agent is the one built at connect."""
        client = LlmClient("t", mode="voice")
        agent = client.agent
        details = {"agent_id": "agent_c5ae", "metadata": {"events_channel": "voice-1"}}

        persona = client.apply_call_details(details)

        assert persona is CLASSIC_PERSONA
        assert client.agent is agent
        assert client.call_details == details
        assert client.draft_begin_message().content == prompts.begin_sentence

    def test_apply_call_details_still_tolerates_a_malformed_call(self):
        client = LlmClient("t", mode="voice")
        assert client.apply_call_details("not a dict") is CLASSIC_PERSONA
        assert client.call_details == {}

    def test_the_classic_judge_reads_the_classic_rubric_only(self):
        assert guardrail.guardrail_agent.instructions == guardrail.GUARDRAIL_INSTRUCTIONS
        assert guardrail.SECT_GUARDRAIL_NOTE not in guardrail.guardrail_agent.instructions

    def test_classic_traces_carry_no_persona_field(self):
        assert LlmClient("t", mode="text")._persona_metadata() == {}

    def test_classic_prompt_cache_keys_are_unchanged(self):
        """The classic agent keeps V4's keys; another persona gets its own cache group."""
        from llm import prompt_cache_key

        assert prompt_cache_key("voice") == "portfolio-agent-voice"
        assert prompt_cache_key("text") == "portfolio-agent-text"
        assert prompt_cache_key("voice", MING_SECT) == "portfolio-agent-voice-ming-sect"
        classic = LlmClient("t", mode="voice").agent.model_settings.extra_args
        sect = LlmClient("t", mode="voice", persona=MING_SECT).agent.model_settings.extra_args
        assert classic["prompt_cache_key"] == "portfolio-agent-voice"
        assert sect["prompt_cache_key"] == "portfolio-agent-voice-ming-sect"


# sha256 of every classic text. The classic persona is what any caller that asks
# for no persona gets, the old site's calls included, so none of these may change
# by accident while the sect persona is worked on. Ported from V4 origin/main
# 564baed (server 5a990aa, the code live on fastapi-ws). If you mean to change
# one, change it in prompts.py / guardrail.py and update its hash here.
CLASSIC_TEXT_SHA256 = {
    "voice_system_prompt": "4803da6c335a1f15caac48f20181dd180f4c879f1a80c51810e385ed064e3491",
    "text_system_prompt": "202db96c28358e07336e953406f17e7c35661c51333c822ddf45c031a423e619",
    "begin_sentence": "3d10d1a9b93220d4fa52c3a7d547a1160f24bc3cedfc6c32eb6085bece0270e2",
    "guardrail_refusal_message": "121a6dac7119258eb2950b3306a9d94d43879bf5b7016a4b6b3d9f44628921e5",
    "guardrail_interruption_message": "db660979562d7a5a0273ac4fed3a2a789a711f3b7afd2fa1752ee056e4308bdf",
    "reminder_checkin_message": "805bb603686aff8c675bac698a2a664ae36614c6d27a7a7bc7b55c02cce59b44",
    "reminder_prompt": "7fd86ada716147088554242530ea481884c822827881d4c15c096c7508d2007f",
}
CLASSIC_RUBRIC_SHA256 = "0a91c1a5162d1a0a337457023022ace3d92dc74e30876c7b1c6738b81a0295ac"
# The live V4 rubric: identical but for the repository it names.
LIVE_V4_RUBRIC_SHA256 = "5bd6c7260d6ef717396ba5457607d0bffa873f13579f3ca74a380b3cfefe7f5e"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestClassicTextsArePinned:
    @pytest.mark.parametrize("name", sorted(CLASSIC_TEXT_SHA256))
    def test_classic_prompt_text(self, name):
        assert _sha256(getattr(prompts, name)) == CLASSIC_TEXT_SHA256[name], (
            f"prompts.{name} changed; the classic persona must not drift by accident"
        )

    def test_classic_persona_uses_the_pinned_texts(self):
        assert _sha256(CLASSIC_PERSONA.voice_system_prompt) == CLASSIC_TEXT_SHA256["voice_system_prompt"]
        assert _sha256(CLASSIC_PERSONA.text_system_prompt) == CLASSIC_TEXT_SHA256["text_system_prompt"]

    def test_classic_rubric(self):
        assert _sha256(guardrail.GUARDRAIL_INSTRUCTIONS) == CLASSIC_RUBRIC_SHA256
        assert _sha256(guardrail.guardrail_agent.instructions) == CLASSIC_RUBRIC_SHA256

    def test_classic_rubric_matches_the_live_one_but_for_the_repo_name(self):
        v4 = guardrail.GUARDRAIL_INSTRUCTIONS.replace("PortfolioV5", "PortfolioV4")
        assert _sha256(v4) == LIVE_V4_RUBRIC_SHA256


# --- the sect persona --------------------------------------------------------


class TestSectClient:
    @pytest.mark.parametrize(
        "mode, prompt",
        [
            ("voice", prompts_sect.sect_voice_system_prompt),
            ("text", prompts_sect.sect_text_system_prompt),
        ],
        ids=["voice", "text"],
    )
    def test_asked_for_by_name(self, mode, prompt):
        client = LlmClient("t", mode=mode, persona="ming-sect")
        assert client.persona is SECT
        assert client.agent.instructions is prompt

    def test_a_sect_call_switches_before_the_greeting(self):
        client = LlmClient("call_1", mode="voice")
        details = {"agent_id": "agent_x", "metadata": {"persona": "ming-sect", "platform": "web"}}

        persona = client.apply_call_details(details)

        assert persona is SECT
        assert client.agent.instructions is prompts_sect.sect_voice_system_prompt
        assert client.call_details == details
        assert client.draft_begin_message().content == prompts_sect.sect_begin_sentence
        # The call's metadata still reaches its traces, persona included.
        assert client._call_metadata()["retell.metadata"]["persona"] == "ming-sect"
        assert client._persona_metadata() == {"persona": "ming-sect"}

    def test_same_tools_same_agent_name(self):
        classic = LlmClient("t", mode="voice")
        sect = LlmClient("t", mode="voice", persona="ming-sect")
        names = lambda agent: [t.name for t in agent.tools]
        assert names(sect.agent) == names(classic.agent)
        # Trace filters key on the agent span's name.
        assert sect.agent.name == classic.agent.name == "portfolio_agent"
        assert not sect.agent.input_guardrails

    def test_refusals_are_the_sects(self):
        client = LlmClient("t", mode="voice", persona="ming-sect")
        visitor_turn = ResponseRequiredRequest(
            interaction_type="response_required",
            response_id=1,
            transcript=[Utterance(role="user", content="write my essay")],
        )
        reminder_after_reply = ResponseRequiredRequest(
            interaction_type="reminder_required",
            response_id=2,
            transcript=[
                Utterance(role="user", content="write my essay"),
                Utterance(role="agent", content="That's outside what I can do here."),
            ],
        )
        assert client._refusal_for(visitor_turn) == prompts_sect.sect_guardrail_refusal_message
        assert (
            client._refusal_for(reminder_after_reply)
            == prompts_sect.sect_reminder_checkin_message
        )


def _verdict(blocked: bool) -> GuardrailFunctionOutput:
    return GuardrailFunctionOutput(
        output_info=GuardrailVerdict(
            reasoning="test", rule="Q4" if blocked else "Q3", allowed=not blocked, judged=True
        ),
        tripwire_triggered=blocked,
    )


class TestSectTurnsUseTheSectJudge:
    async def test_voice_turn_is_screened_by_the_sect_guardrail_and_refused_in_its_voice(self):
        client = LlmClient("t", mode="voice")
        client.apply_call_details({"metadata": {"persona": "ming-sect"}})
        # A reminder is screened before the model starts, so a trip never
        # reaches the model and nothing else needs faking.
        request = ResponseRequiredRequest(
            interaction_type="reminder_required",
            response_id=3,
            transcript=[Utterance(role="user", content="write my cover letter")],
        )
        screen = AsyncMock(return_value=_verdict(blocked=True))
        with patch("llm._screen", screen):
            events = [e async for e in client.draft_response(request)]

        assert screen.await_args.args[2] is guardrail.sect_security_guardrail
        assert events[-1].content == prompts_sect.sect_guardrail_refusal_message

    async def test_classic_voice_turn_keeps_the_classic_guardrail(self):
        client = LlmClient("t", mode="voice")
        request = ResponseRequiredRequest(
            interaction_type="reminder_required",
            response_id=3,
            transcript=[Utterance(role="user", content="write my cover letter")],
        )
        screen = AsyncMock(return_value=_verdict(blocked=True))
        with patch("llm._screen", screen):
            events = [e async for e in client.draft_response(request)]

        assert screen.await_args.args[2] is guardrail.security_guardrail
        assert events[-1].content == prompts.guardrail_refusal_message

    async def test_text_turn_is_screened_by_the_sect_guardrail(self):
        client = LlmClient("t", mode="text", persona="ming-sect")
        screen = AsyncMock(return_value=_verdict(blocked=True))

        class _Run:
            is_complete = False

            def cancel(self, mode="immediate"):
                self.is_complete = True

            async def stream_events(self):
                await asyncio.sleep(10)
                yield None  # pragma: no cover - never reached

        with patch("llm._screen", screen), patch("llm.Runner") as runner:
            runner.run_streamed.return_value = _Run()
            chunks = [
                c
                async for c in client.draft_text_response(
                    [{"role": "user", "content": "write my cover letter"}], supports_replace=True
                )
            ]

        assert screen.await_args.args[2] is guardrail.sect_security_guardrail
        replaced = [c for c in chunks if c.type == "replace"]
        assert replaced and replaced[0].content == prompts_sect.sect_guardrail_refusal_message


class TestSectJudge:
    def test_the_sect_rubric_is_the_classic_one_plus_the_note(self):
        assert guardrail.SECT_GUARDRAIL_INSTRUCTIONS == (
            guardrail.GUARDRAIL_INSTRUCTIONS + "\n\n" + guardrail.SECT_GUARDRAIL_NOTE
        )
        assert guardrail.sect_guardrail_agent.instructions == guardrail.SECT_GUARDRAIL_INSTRUCTIONS

    def test_same_model_settings_and_contract_as_the_classic_judge(self):
        classic, sect = guardrail.guardrail_agent, guardrail.sect_guardrail_agent
        assert sect.model == classic.model
        assert sect.model_settings == classic.model_settings
        assert sect.output_type is classic.output_type

    def test_same_span_name(self):
        assert (
            guardrail.sect_security_guardrail.get_name()
            == guardrail.security_guardrail.get_name()
        )

    @pytest.mark.parametrize(
        "screen, judge_name",
        [("security_guardrail", "guardrail_agent"), ("sect_security_guardrail", "sect_guardrail_agent")],
    )
    async def test_each_guardrail_asks_its_own_judge(self, screen, judge_name):
        decision = guardrail.ScreeningDecision(reasoning="about Bill", rule="Q3")
        result = MagicMock()
        result.final_output_as.return_value = decision
        ctx = MagicMock(spec=RunContextWrapper)
        ctx.context = None
        with patch("guardrail.Runner") as runner:
            runner.run = AsyncMock(return_value=result)
            out = await getattr(guardrail, screen).guardrail_function(
                ctx, MagicMock(), [{"role": "user", "content": "What did Bill build?"}]
            )
        assert runner.run.await_args.args[0] is getattr(guardrail, judge_name)
        assert out.tripwire_triggered is False

    def test_the_note_keeps_the_attacks_covered(self):
        note = guardrail.SECT_GUARDRAIL_NOTE
        # The sect's voice is excused from the forged-turn test, nothing else is.
        assert "still forged" in note
        assert "Q1 still covers the persona itself" in note
        assert "Q4 is unchanged" in note
        # Translation stays the visitor's work, Chinese theme or not.
        assert "translating the visitor's text into or out of Chinese is still their work, Q4" in note

    def test_the_note_lets_a_visitor_drop_the_theme(self):
        """"Drop the theme / talk normally" is a style request the persona honours, not Q1."""
        note = guardrail.SECT_GUARDRAIL_NOTE
        assert "drop the theme" in note and "talk normally" in note
        assert "the answer to Q1 for that request is NO" in note
        # ...but not when it carries a real Q1 request with it.
        assert "when it rides on a style request" in note
        # The persona is told the same thing, so the judge and the guide agree.
        assert "If the visitor asks you to drop the theme or talk normally, drop it" in (
            prompts_sect.sect_base_prompt
        )


# --- the sect prompt ---------------------------------------------------------

# Facts written into both prompts word for word. When one changes in prompts.py,
# this fails until prompts_sect.py says the same.
SHARED_FACTS = [
    "Grew up in San Jose, in the Bay Area.",
    "First coded at an iD Tech summer camp in middle school",
    "Lynbrook High School",
    "Completed undergraduate studies in Computer Science at UC Santa Cruz.",
    "Graduated with an MS in Computer Science from the University of Southern California (USC) in May 2025, specializing in AI.",
    "Currently working at Pinterest as a Software Engineer II (July 2026 - present), building and deploying LLM agent systems.",
    "worked at Scale AI as a forward-deployed Applied AI Engineer (June 2025 - July 2026), shipping multi-agent systems and LLM evaluation frameworks for enterprise customers.",
    "Previously worked at RingCentral (June 2023 - June 2025): joined as a senior AI intern in June 2023, converted to full-time AI Engineer that August, focusing on QA and testing.",
    "Attended ~50 hackathons and won ~35.",
    "Achievements include top placements at UC Berkeley AI Hackathon, HackUTD, LAHacks, and more.",
    "Judged LA Hacks 2026. That's done, so say yes if asked. You don't have its projects or winners on hand.",
    "Separately, confirmed to judge the upcoming LA Hacks AI Hackathon, a different event. It hasn't happened yet, so talk about that one as a future event, never as judging already done.",
    "Numbers you can quote: a multi-agent system that automates denied-claim investigations (3 sub-agents, 20 policy workflows) that scaled to 300-500 weekly users and up to 20K claims a week, and an LLM-as-judge eval framework that took QA-audit accuracy from 64% to 88%.",
    "that this website replaced. It was overly complicated and had too many moving parts.",
    "billzhangsc@gmail.com",
    "around the average for the role in San Francisco",
    "the replies come from OpenAI's GPT-5.6. Fine to say if asked.",
    '500+ new connection requests overnight',
    '"Prepare for the worst, hope for the best."',
    '"Never Split the Difference',
    "Halo, Mass Effect, Stargate",
    "Next.js 15 + React 19 + shadcn/ui, hosted on Vercel",
    "Pinecone vector database with 52+ project embeddings (text-embedding-3-large)",
    'AdaptEd → "teachme-3p7bw1"',
    'Dispatch AI → "dispatch-ai"',
    'TalkTuahBank → "talktuahbank"',
    "CRITICAL: The project_id MUST be an exact ID returned by search_projects",
    "Never call get_project_details without also calling display_project.",
]


def _flagship_block(prompt: str) -> str:
    """The body of the classic prompt's flagship-projects section."""
    after = prompt.split("### **12. DEFAULT BEST PROJECTS**", 1)[1]
    return after.split("### **13.", 1)[0].strip()


# The flagship block's lines that the classic prompt says to Bill ("you ran it"),
# as the guide says them about him. Everything else is copied word for word.
THIRD_PERSON = {
    "you ran it as a startup": "he ran it as a startup",
}


class TestSectPromptFacts:
    @pytest.mark.parametrize("fact", SHARED_FACTS)
    def test_fact_matches_the_classic_prompt(self, fact):
        assert fact in prompts.base_prompt, f"no longer in prompts.py: {fact!r}"
        assert fact in prompts_sect.sect_base_prompt, f"prompts_sect.py is stale: {fact!r}"

    def test_flagship_projects_are_copied_word_for_word(self):
        block = _flagship_block(prompts.base_prompt)
        assert "never call it a $50K grand prize" in block
        for second, third in THIRD_PERSON.items():
            assert second in block, f"no longer in prompts.py: {second!r}"
            block = block.replace(second, third)
        assert block in prompts_sect.sect_base_prompt

    @pytest.mark.parametrize(
        "tool",
        [
            "display_landing_page",
            "display_homepage",
            "display_resume_page",
            "display_hackathons_page",
            "display_education_page",
            "display_architecture_page",
            "display_experience_page",
            "display_skills_page",
            "display_personal_page",
            "display_projects_page",
            "display_project",
            "search_projects",
            "get_project_details",
        ],
    )
    def test_every_tool_is_described(self, tool):
        assert f"#### {tool}(" in prompts_sect.sect_base_prompt


class TestSectPromptRole:
    def test_it_is_a_guide_never_bill(self):
        base = prompts_sect.sect_base_prompt
        assert "You are not Bill." in base
        assert "Speak about Bill in the third person" in base
        assert 'You are "Bill Zhang,"' not in base

    def test_no_caricature(self):
        assert "Never: a fake accent, pidgin or broken English" in prompts_sect.sect_base_prompt

    def test_chinese_always_comes_with_its_meaning(self):
        assert "always followed by its English meaning" in prompts_sect.sect_base_prompt

    def test_voice_mode_asks_for_pinyin_not_characters(self):
        assert "NEVER write Chinese characters" in prompts_sect.sect_voice_system_prompt
        assert "NEVER write Chinese characters" not in prompts_sect.sect_text_system_prompt

    @pytest.mark.parametrize(
        "line",
        [
            prompts_sect.sect_begin_sentence,
            prompts_sect.sect_guardrail_refusal_message,
            prompts_sect.sect_guardrail_interruption_message,
            prompts_sect.sect_reminder_checkin_message,
        ],
    )
    def test_fixed_lines_are_speakable(self, line):
        """Read by an English TTS voice: no Chinese characters, no markdown."""
        assert not _CJK.search(line)
        assert not re.search(r"[*_`#\[\]]", line)

    def test_refusals_name_the_hobbies(self):
        """Same rule as the classic refusal (issue #10): music is on-topic."""
        for line in (
            prompts_sect.sect_guardrail_refusal_message,
            prompts_sect.sect_guardrail_interruption_message,
            prompts_sect.sect_reminder_checkin_message,
        ):
            assert "music" in line and "Bill" in line

    def test_interruption_cannot_fuse_onto_a_cut_off_word(self):
        assert prompts_sect.sect_guardrail_interruption_message.startswith(" ")


# --- the sect's places match the client's --------------------------------------

_CLIENT = Path(__file__).resolve().parents[2] / "client" / "src" / "lib"
_AREAS_TS = _CLIENT / "sect" / "areas.ts"
_VOICE_BUS_TS = _CLIENT / "voice-bus.ts"

needs_client = pytest.mark.skipif(
    not (_AREAS_TS.exists() and _VOICE_BUS_TS.exists()),
    reason="the client source is not next to the server",
)


def _client_areas() -> dict[str, dict[str, str]]:
    """area id -> {sectionId, label, zh}, from client/src/lib/sect/areas.ts."""
    pattern = re.compile(
        r'\{\s*id:\s*"(\w+)",\s*sectionId:\s*"(\w+)",\s*label:\s*"([^"]+)",\s*zh:\s*"([^"]+)"\s*\}'
    )
    return {
        m[1]: {"sectionId": m[2], "label": m[3], "zh": m[4]}
        for m in pattern.finditer(_AREAS_TS.read_text(encoding="utf-8"))
    }


def _page_to_section() -> dict[str, str]:
    """Server page value -> main-page section id, from voice-bus.ts PAGE_TO_SECTION."""
    text = _VOICE_BUS_TS.read_text(encoding="utf-8")
    block = text.split("PAGE_TO_SECTION", 1)[1].split("};", 1)[0]
    return dict(re.findall(r'(\w+):\s*"(\w+)"', block))


@needs_client
class TestSectPlacesMatchTheClient:
    def test_every_place_is_named_with_its_chinese(self):
        areas = _client_areas()
        assert len(areas) == 11
        for area in areas.values():
            assert f"**{area['label']}** ({area['zh']}," in prompts_sect.sect_base_prompt

    def test_each_tool_flies_where_the_prompt_says(self):
        """navigation.py page -> voice-bus section -> sect area -> the prompt's place line."""
        from navigation import _PAGE_TOOLS

        areas = _client_areas()
        by_section = {a["sectionId"]: a for a in areas.values()}
        page_to_section = _page_to_section()
        tools = dict(_PAGE_TOOLS)
        tools["display_project"] = "project"

        for tool, page in tools.items():
            area = by_section[page_to_section[page]]
            line = next(
                line
                for line in prompts_sect.sect_base_prompt.splitlines()
                if line.lstrip().startswith(("1", "2", "3", "4", "5", "6", "7", "8", "9"))
                and f"**{area['label']}**" in line
            )
            assert f"Tool: {tool}" in line, (tool, area["label"], line)


# The sect is the home page, so its title is the site's, in the root layout.
_TITLE_TSX = _CLIENT.parent / "app" / "layout.tsx"
_LORE_TS = _CLIENT / "sect" / "lore.ts"


@pytest.mark.skipif(not _TITLE_TSX.exists(), reason="the client source is not next to the server")
class TestSectNameMatchesTheClient:
    """The sect has been renamed before; a rename on the page must reach the persona too."""

    def test_the_persona_uses_the_page_titles_name(self):
        text = _TITLE_TSX.read_text(encoding="utf-8")
        m = re.search(r"const TITLE = `[^`\n]*· (?:The )?([^`\n]+)`", text)
        assert m, "can't find the sect's English name in client/src/app/layout.tsx TITLE"
        name = m[1].strip()
        for where, prompt in (
            ("sect_begin_sentence", prompts_sect.sect_begin_sentence),
            ("sect_base_prompt", prompts_sect.sect_base_prompt),
            ("SECT_GUARDRAIL_NOTE", guardrail.SECT_GUARDRAIL_NOTE),
        ):
            assert name in prompt, f"the site's title calls it {name!r}; {where} doesn't"


@pytest.mark.skipif(not _LORE_TS.exists(), reason="the client source is not next to the server")
class TestSectLoreMatchesTheClient:
    def test_text_mode_spells_each_reference_as_the_scene_does(self):
        """lore.ts writes the novels' names in traditional characters; text chat copies them."""
        # The cards' entries only (LORE), not the star and art labels further down.
        lore = _LORE_TS.read_text(encoding="utf-8").split("export const LORE = {", 1)[1]
        lore = lore.split("} as const satisfies", 1)[0]
        names = re.findall(r'zh:\s*"([^"]+)"', lore)
        assert len(names) >= 10
        for zh in names:
            assert zh in prompts_sect.sect_text_system_prompt, zh


# --- the endpoints pass the persona through ------------------------------------


class TestChatEndpointPersona:
    def _post(self, app_client, **extra):
        seen = []

        def fake_client(*args, **kwargs):
            seen.append(kwargs.get("persona"))
            instance = MagicMock()

            async def draft_text_response(messages, supports_replace):
                from custom_types import TextChatStreamChunk

                yield TextChatStreamChunk(type="done")

            instance.draft_text_response = draft_text_response
            return instance

        with patch("main.LlmClient", side_effect=fake_client):
            response = app_client.post(
                "/chat", json={"messages": [{"role": "user", "content": "Hi"}], **extra}
            )
        return response, seen

    def test_no_persona_field_means_none(self, app_client):
        response, seen = self._post(app_client)
        assert response.status_code == 200
        assert seen == [None]

    def test_persona_is_handed_to_the_client(self, app_client):
        response, seen = self._post(app_client, persona="ming-sect")
        assert response.status_code == 200
        assert seen == ["ming-sect"]

    def test_an_unknown_persona_is_not_an_error(self, app_client):
        """LlmClient falls back to classic; the request itself is fine."""
        response, seen = self._post(app_client, persona="some-future-persona")
        assert response.status_code == 200
        assert seen == ["some-future-persona"]

    def test_an_oversized_persona_is_rejected(self, app_client):
        response, _ = self._post(app_client, persona="x" * 33)
        assert response.status_code == 422


def _voice_socket_path() -> str:
    """The voice websocket route, read from the app (its prefix is a secret)."""
    from starlette.routing import WebSocketRoute

    from main import app

    route = next(r for r in app.routes if isinstance(r, WebSocketRoute))
    return route.path.replace("{call_id}", "call_test")


class TestVoiceSocketPersona:
    def _greeting(self, app_client, call: dict) -> str:
        with app_client.websocket_connect(_voice_socket_path()) as ws:
            config = ws.receive_json()
            assert config["response_type"] == "config"
            assert config["config"]["call_details"] is True
            ws.send_json({"interaction_type": "call_details", "call": call})
            first = ws.receive_json()
        assert first["response_type"] == "response" and first["content_complete"] is True
        return first["content"]

    def test_an_old_site_call_is_greeted_by_bill(self, app_client):
        call = {"call_id": "call_test", "metadata": {"platform": "web", "events_channel": "v-1"}}
        assert self._greeting(app_client, call) == prompts.begin_sentence

    def test_a_sect_call_is_greeted_by_the_sound_transmission(self, app_client):
        call = {"call_id": "call_test", "metadata": {"platform": "web", "persona": "ming-sect"}}
        assert self._greeting(app_client, call) == prompts_sect.sect_begin_sentence
