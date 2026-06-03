from the_scraper.analysis import analyze_with_rules
from the_scraper.models import InstagramPost


def test_rule_analysis_detects_reporting() -> None:
    post = InstagramPost(
        id="adl:test",
        account="adl",
        account_url="https://www.instagram.com/adl/",
        post_url="https://www.instagram.com/p/test/",
        caption="If you see antisemitism, report it through our incident form.",
    )

    analysis = analyze_with_rules(post)

    assert analysis.category == "Reporting"
    assert analysis.equips_followers is True
    assert analysis.actionability_score == 5
