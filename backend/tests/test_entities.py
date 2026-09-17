"""Tests for entity-match word-boundary regex."""

from __future__ import annotations

from parallax.ingestion.entities import matches_critical_entity


class TestMatchesCriticalEntity:
    def test_matches_known_entity(self):
        assert matches_critical_entity("IRGC ships deployed to Hormuz") is True

    def test_matches_case_insensitive(self):
        assert matches_critical_entity("centcom briefing") is True

    def test_does_not_match_oil_inside_boil(self):
        """Regression: substring 'oil' must not match inside unrelated words."""
        assert matches_critical_entity("Water comes to a boil") is False

    def test_does_not_match_iran_inside_iranian(self):
        """Substring 'iran' must not match inside 'iranian'. The bare keyword
        'iran' is not in CRITICAL_ENTITIES, but this guards against substring
        false-positives for any other partial entity matches."""
        assert matches_critical_entity("Cooking iranian recipe today") is False

    def test_matches_persian_gulf_multi_word(self):
        assert matches_critical_entity("incident in the Persian Gulf today") is True

    def test_matches_multi_word_strait_of_hormuz(self):
        assert matches_critical_entity("traffic in the Strait of Hormuz halted") is True

    def test_matches_phrase_when_separated_by_space(self):
        # "tanker seizure" matches when written normally; hyphen vs space matters
        assert matches_critical_entity("Tanker seizure reports rising") is True

    def test_does_not_match_partial_word(self):
        """'Carrier' alone shouldn't match 'carrier group'."""
        assert matches_critical_entity("aircraft carrier deployed") is False

    def test_matches_carrier_group_phrase(self):
        assert matches_critical_entity("US carrier group near coast") is True

    def test_empty_input(self):
        assert matches_critical_entity("") is False

    def test_no_entities_present(self):
        assert matches_critical_entity("The cat sat on the mat") is False
