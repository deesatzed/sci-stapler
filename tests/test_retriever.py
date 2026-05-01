"""Tests for the retriever module."""

import pytest

from agentmedq.models import Source
from agentmedq.retriever import _detect_source


class TestDetectSource:
    def test_pmc_id(self):
        assert _detect_source("PMC1234567") == Source.PMC
        assert _detect_source("pmc9999") == Source.PMC

    def test_arxiv_id(self):
        assert _detect_source("2301.12345") == Source.ARXIV
        assert _detect_source("2301.12345v2") == Source.ARXIV

    def test_openalex_id(self):
        assert _detect_source("W1234567890") == Source.OPENALEX

    def test_preprint_id(self):
        assert _detect_source("PPR123456") == Source.BIORXIV

    def test_doi_biorxiv(self):
        assert _detect_source("10.1101/2024.01.01.123456") == Source.BIORXIV

    def test_unknown(self):
        assert _detect_source("unknown_format") is None

    def test_empty(self):
        assert _detect_source("") is None
