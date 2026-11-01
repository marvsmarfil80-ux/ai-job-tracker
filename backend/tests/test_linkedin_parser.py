import pytest

from app.services.linkedin_parser import LinkedInParseError, parse_linkedin_alert


def link(job_id, host="www.linkedin.com", comm=True):
    path = "comm/jobs/view" if comm else "jobs/view"
    return f"https://{host}/{path}/{job_id}/?trackingId=abc&amp;refId=xyz"


def card(
    title,
    company="Example Corp",
    location="Manila, Philippines",
    mode="Remote",
    job_id=1000001,
    **link_options,
):
    meta = f"{company}   {location}"
    if mode:
        meta = f"{meta} ({mode})"
    return (
        f'<tr><td><a href="{link(job_id, **link_options)}">{title}</a></td></tr>'
        f"<tr><td>{meta}</td></tr>"
    )


def page(*cards, extra=""):
    return f"<html><body>{extra}<table>{''.join(cards)}</table></body></html>"


def test_parses_multiple_jobs():
    html = page(
        card("Support Agent", job_id=1),
        card("Data Entry Clerk", company="Sample Inc", location="Cebu", mode="Hybrid", job_id=2),
        card("Admin Assistant", mode=None, job_id=3),
    )
    result = parse_linkedin_alert(html)
    assert [job.title for job in result.jobs] == [
        "Support Agent",
        "Data Entry Clerk",
        "Admin Assistant",
    ]
    first = result.jobs[0]
    assert first.company == "Example Corp"
    assert first.location == "Manila, Philippines"
    assert first.work_mode == "remote"
    assert first.url == "https://www.linkedin.com/jobs/view/1/"
    assert result.jobs[1].company == "Sample Inc"
    assert result.jobs[1].work_mode == "hybrid"
    assert result.jobs[2].work_mode is None
    assert result.jobs[2].location == "Manila, Philippines"
    assert result.skipped == 0
    assert result.truncated is False


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Remote", "remote"),
        ("Hybrid", "hybrid"),
        ("On-site", "on_site"),
        ("on-site", "on_site"),
        (None, None),
    ],
)
def test_work_mode_mapping(label, expected):
    result = parse_linkedin_alert(page(card("Support Agent", mode=label)))
    assert result.jobs[0].work_mode == expected
    assert result.jobs[0].location == "Manila, Philippines"


@pytest.mark.parametrize("comm", [True, False])
def test_both_link_types_are_normalized(comm):
    result = parse_linkedin_alert(page(card("Support Agent", job_id=777, comm=comm)))
    assert result.jobs[0].url == "https://www.linkedin.com/jobs/view/777/"


def test_non_linkedin_links_are_ignored():
    html = page(
        card("Fake One", job_id=5, host="evil.example.com"),
        card("Fake Two", job_id=6, host="www.linkedin.com.evil.example.com"),
        card("Fake Three", job_id=8, host="www.linkedin.com@evil.example.com"),
        card("Real Job", job_id=7),
    )
    result = parse_linkedin_alert(html)
    assert [job.title for job in result.jobs] == ["Real Job"]


def test_job_without_title_is_skipped_and_counted():
    empty = (
        f'<tr><td><a href="{link(9)}"></a></td></tr>'
        "<tr><td>Example Corp   Cebu (Remote)</td></tr>"
    )
    result = parse_linkedin_alert(page(empty, card("Real Job", job_id=10)))
    assert [job.title for job in result.jobs] == ["Real Job"]
    assert result.skipped == 1


def test_long_fields_are_truncated_to_200():
    html = page(card("T" * 300, company="C" * 300, location="L" * 300))
    job = parse_linkedin_alert(html).jobs[0]
    assert len(job.title) == 200
    assert len(job.company) == 200
    assert len(job.location) == 200


def test_more_than_50_jobs_are_truncated():
    cards = [card(f"Job {number}", job_id=number + 100) for number in range(60)]
    result = parse_linkedin_alert(page(*cards))
    assert len(result.jobs) == 50
    assert result.truncated is True


@pytest.mark.parametrize(
    "html",
    [
        "",
        "   ",
        "<html><body><p>Hello there</p></body></html>",
        page(card("Fake Job", host="evil.example.com")),
    ],
)
def test_unexpected_shape_raises_clear_error(html):
    with pytest.raises(LinkedInParseError):
        parse_linkedin_alert(html)


def test_script_and_hidden_text_are_not_used():
    extra = (
        '<script>var u = "https://www.linkedin.com/jobs/view/999/";</script>'
        "<style>.x { color: red }</style>"
        '<div style="display:none">HIDDEN-BLOCK</div>'
        "<span hidden>HIDDEN-ATTR</span>"
    )
    title = 'Support <span style="display:none">HIDDEN-TITLE</span>Agent'
    result = parse_linkedin_alert(page(card(title, job_id=11), extra=extra))
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.title == "Support Agent"
    assert job.url == "https://www.linkedin.com/jobs/view/11/"
    for value in (job.title, job.company, job.location, job.url):
        assert "HIDDEN" not in (value or "")


def test_html_entities_are_decoded():
    result = parse_linkedin_alert(
        page(card("Support &amp; Admin Assistant", company="Caf&eacute; Corp"))
    )
    assert result.jobs[0].title == "Support & Admin Assistant"
    assert result.jobs[0].company == "Café Corp"


def test_layout_with_generic_link_text():
    html = (
        "<html><body><table>"
        "<tr><td>Remote Support Agent</td></tr>"
        "<tr><td>Example Corp   Manila (Remote)</td></tr>"
        f'<tr><td><a href="{link(31)}">View job</a></td></tr>'
        "</table></body></html>"
    )
    job = parse_linkedin_alert(html).jobs[0]
    assert job.title == "Remote Support Agent"
    assert job.company == "Example Corp"
    assert job.location == "Manila"
    assert job.work_mode == "remote"
    assert job.url == "https://www.linkedin.com/jobs/view/31/"


def test_duplicate_link_in_one_email_gives_one_job():
    result = parse_linkedin_alert(
        page(card("Support Agent", job_id=21), card("Same Job Again", job_id=21))
    )
    assert len(result.jobs) == 1
    assert result.jobs[0].title == "Support Agent"


def test_meta_without_location():
    result = parse_linkedin_alert(page(card("Support Agent", location="")))
    job = result.jobs[0]
    assert job.company == "Example Corp"
    assert job.location is None
    assert job.work_mode == "remote"


def test_control_and_invisible_characters_are_removed():
    result = parse_linkedin_alert(page(card("Sup\u200bport\x00 Agent\x07")))
    assert result.jobs[0].title == "Support Agent"