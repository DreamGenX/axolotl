"""Module for testing prompt tokenizers."""

import json
import logging
import unittest
from pathlib import Path

import pytest
from datasets import load_dataset
from transformers import AddedToken, AutoTokenizer, LlamaTokenizer
from utils import enable_hf_offline

from axolotl.prompt_strategies.alpaca_chat import NoSystemPrompter
from axolotl.prompt_strategies.alpaca_w_system import (
    InstructionWSystemPromptTokenizingStrategy,
    SystemDataPrompter,
)
from axolotl.prompt_strategies.llama2_chat import (
    Llama2ChatPrompter,
    LLama2ChatTokenizingStrategy,
)
from axolotl.prompt_strategies.orpo.chat_template import load
from axolotl.prompt_tokenizers import AlpacaPromptTokenizingStrategy
from axolotl.prompters import AlpacaPrompter, PromptStyle
from axolotl.utils.dict import DictDefault

LOG = logging.getLogger("axolotl")

test_data = {
    "multi_turn_sys": {
        "conversations": [
            {"from": "system", "value": "lorem"},
            {"from": "human", "value": "abc"},
            {"from": "gpt", "value": "ipsum"},
            {"from": "human", "value": "123"},
            {"from": "gpt", "value": "sit"},
        ]
    },
    "single_turn_sys": {
        "conversations": [
            {"from": "system", "value": "lorem"},
            {"from": "human", "value": "abc"},
            {"from": "gpt", "value": "ipsum"},
        ]
    },
    "single_turn_no_sys": {
        "conversations": [
            {"from": "human", "value": "abc"},
            {"from": "gpt", "value": "ipsum"},
        ]
    },
    "multi_turn_no_sys": {
        "conversations": [
            {"from": "human", "value": "abc"},
            {"from": "gpt", "value": "ipsum"},
            {"from": "human", "value": "123"},
            {"from": "gpt", "value": "sit"},
        ]
    },
}


class TestPromptTokenizationStrategies(unittest.TestCase):
    """
    Test class for prompt tokenization strategies.
    """

    @enable_hf_offline
    def setUp(self) -> None:
        # pylint: disable=duplicate-code
        self.tokenizer = AutoTokenizer.from_pretrained("huggyllama/llama-7b")
        self.tokenizer.add_special_tokens(
            {
                "bos_token": "<s>",
                "eos_token": "</s>",
                "unk_token": "<unk>",
            }
        )

    def test_no_sys_prompt(self):
        """
        tests the interface between the user and assistant parts
        """
        prompter = NoSystemPrompter()
        # pylint: disable=duplicate-code
        strat = AlpacaPromptTokenizingStrategy(
            prompter,
            self.tokenizer,
            False,
            2048,
        )
        sample = {
            "instruction": "hello cruel. lorem ipsum dolor sit amet.",
            "output": "world!",
        }
        example = strat.tokenize_prompt(sample)
        world_idx = example["input_ids"].index(3186)
        assert example["labels"][world_idx] == 3186
        assert example["labels"][world_idx - 1] == -100

    def test_alpaca(self):
        """
        tests the interface between the user and assistant parts
        """
        # pylint: disable=duplicate-code
        prompter = AlpacaPrompter()
        strat = AlpacaPromptTokenizingStrategy(
            prompter,
            self.tokenizer,
            False,
            2048,
        )
        sample = {"instruction": "hello!", "output": "Hi! How can I help?"}
        example = strat.tokenize_prompt(sample)
        world_idx = example["input_ids"].index(6324)
        assert example["labels"][world_idx] == 6324
        assert example["labels"][world_idx - 1] == -100


class InstructionWSystemPromptTokenizingStrategyTest(unittest.TestCase):
    """
    Test class for prompt tokenization strategies with sys prompt from the dataset
    """

    @enable_hf_offline
    def setUp(self) -> None:
        # pylint: disable=duplicate-code
        self.tokenizer = AutoTokenizer.from_pretrained("huggyllama/llama-7b")
        self.tokenizer.add_special_tokens(
            {
                "bos_token": "<s>",
                "eos_token": "</s>",
                "unk_token": "<unk>",
            }
        )

    def test_system_alpaca(self):
        prompter = SystemDataPrompter(PromptStyle.CHAT.value)
        strat = InstructionWSystemPromptTokenizingStrategy(
            prompter,
            self.tokenizer,
            False,
            2048,
        )
        sample = {
            "system": "use cot",
            "instruction": "hello!",
            "output": "Hi! How can I help?",
        }
        example = strat.tokenize_prompt(sample)
        assert example["input_ids"][0:5] == [
            1,
            28962,
            1254,
            12665,
            29901,
        ]  # "<s>SYSTEM:"
        assert example["input_ids"][5:7] == [671, 20118]  # " use cot"
        assert example["input_ids"][8] == 11889  # USER


class Llama2ChatTokenizationTest(unittest.TestCase):
    """
    Test class for prompt tokenization strategies with sys prompt from the dataset
    """

    @enable_hf_offline
    def setUp(self) -> None:
        # pylint: disable=duplicate-code
        self.tokenizer = LlamaTokenizer.from_pretrained("NousResearch/Llama-2-7b-hf")
        # woraround because official Meta repos are not open

    def test_llama2_chat_integration(self):
        with open(
            Path(__file__).parent / "fixtures/conversation.json", encoding="utf-8"
        ) as fin:
            data = fin.read()
            conversation = json.loads(data)
        with open(
            Path(__file__).parent / "fixtures/conversation.tokenized_llama2chat.json",
            encoding="utf-8",
        ) as fin:
            data = fin.read()
            tokenized_conversation = json.loads(data)
        prompter = Llama2ChatPrompter()
        strat = LLama2ChatTokenizingStrategy(
            prompter,
            self.tokenizer,
            False,
            4096,
        )
        example = strat.tokenize_prompt(conversation)
        for fields in ["input_ids", "attention_mask", "labels"]:
            self.assertEqual(len(example[fields]), len(tokenized_conversation[fields]))
            self.assertEqual(example[fields], tokenized_conversation[fields])

    def compare_with_transformers_integration(self):
        # this needs transformers >= v4.31.0
        from transformers.models.llama.tokenization_llama import B_SYS, E_SYS
        from transformers.pipelines.conversational import Conversation

        # from transformers.models.llama.tokenization_llama import DEFAULT_SYSTEM_PROMPT
        # broken as of 23/7/20
        # see https://github.com/huggingface/transformers/pull/24935
        # pylint: disable=C0103
        DEFAULT_SYSTEM_PROMPT = """\
You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.

If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information."""
        with open(
            Path(__file__).parent / "fixtures/conversation.json", encoding="utf-8"
        ) as fin:
            data = fin.read()
            conversation = json.loads(data)
        with open(
            Path(__file__).parent / "fixtures/conversation.tokenized_llama2chat.json",
            encoding="utf-8",
        ) as fin:
            data = fin.read()
            tokenized_conversation = json.loads(data)

        user_input = []
        answers = []
        for msg in conversation["conversations"]:
            if msg["from"] == "human":
                user_input.append(msg["value"])
            else:
                answers.append(msg["value"])
        hf_conf = Conversation(
            text=user_input[-1],
            past_user_inputs=[B_SYS + DEFAULT_SYSTEM_PROMPT + E_SYS + user_input[0]]
            + user_input[1:-1],
            generated_responses=answers,
        )
        # pylint: disable=W0212
        hf_tokens = self.tokenizer._build_conversation_input_ids(hf_conf)

        self.assertEqual(
            hf_tokens, tokenized_conversation["input_ids"][: len(hf_tokens)]
        )


class OrpoTokenizationTest(unittest.TestCase):
    """test case for the ORPO tokenization"""

    @enable_hf_offline
    def setUp(self) -> None:
        # pylint: disable=duplicate-code
        tokenizer = LlamaTokenizer.from_pretrained(
            "casperhansen/mistral-7b-instruct-v0.1-awq"
        )
        tokenizer.add_special_tokens(
            {
                "eos_token": AddedToken(
                    "<|im_end|>", rstrip=False, lstrip=False, normalized=False
                )
            }
        )
        tokenizer.add_tokens(
            [
                AddedToken(
                    "<|im_start|>", rstrip=False, lstrip=False, normalized=False
                ),
            ]
        )
        self.tokenizer = tokenizer
        self.dataset = load_dataset(
            "argilla/ultrafeedback-binarized-preferences-cleaned", split="train"
        ).select([0])

    @pytest.mark.skip(reason="TODO: fix hf hub offline to work with HF rate limits")
    def test_orpo_integration(self):
        strat = load(
            self.tokenizer,
            DictDefault({"train_on_inputs": False}),
            DictDefault({"chat_template": "chatml"}),
        )
        res = strat.tokenize_prompt(self.dataset[0])
        assert "rejected_input_ids" in res
        assert "rejected_labels" in res
        assert "input_ids" in res
        assert "labels" in res
        assert "prompt_attention_mask" in res

        assert len(res["rejected_input_ids"]) == len(res["rejected_labels"])
        assert len(res["input_ids"]) == len(res["labels"])
        assert len(res["input_ids"]) == len(res["prompt_attention_mask"])

        assert res["rejected_labels"][0] == -100
        assert res["rejected_input_ids"][-1] == res["rejected_labels"][-1]

        assert res["labels"][0] == -100
        assert res["input_ids"][-1] == res["labels"][-1]

        assert res["prompt_attention_mask"][0] == 1
        assert res["prompt_attention_mask"][-1] == 0


if __name__ == "__main__":
    unittest.main()
