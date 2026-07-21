"""Tests for the rule-aware chunker, on real CONC 3.3 provisions fetched from
https://api-handbook.fca.org.uk/Handbook/GetAllHandBookProvisionsSortedOrderByChapter/conc3
"""

import pytest

from sentinel.chunk import chunk_provisions

SOURCE_URL = "https://api-handbook.fca.org.uk/Handbook/GetAllHandBookProvisionsSortedOrderByChapter/conc3"
RETRIEVED_ON = "2026-07-21"

# Two real provisions of CONC 3.3 (one Rule, one Guidance), fields as returned by the API.
PROVISIONS = [{'contentText': '(1) A firm must ensure that a communication or a financial promotion is clear, '
                 'fair, and not misleading. [Note: paragraphs 2.2 of ILG, 3.16 of DMG and 3.1 of '
                 'CBG]\n'
                 '\n'
                 '(1A) A firm must ensure that each communication and each financial promotion: '
                 '(a) is clearly identifiable as such; (b) is accurate; (c) is balanced and, in '
                 'particular, does not emphasise any potential benefits of a product or service '
                 'without also giving a fair and prominent indication of any relevant risks; (d) '
                 'is sufficient for, and presented in a way that is likely to be understood by, '
                 'the average member of the group to which it is directed, or by which it is '
                 'likely to be received; and (e) does not disguise, omit, diminish or obscure '
                 'important information, statements or warnings.\n'
                 '\n'
                 '(1B) A firm must ensure that, where a communication or financial promotion '
                 'contains a comparison or contrast, the comparison or contrast is presented in a '
                 'fair and balanced way and is meaningful.\n'
                 '\n'
                 '(2) If, for a particular communication or financial promotion, a firm takes '
                 'reasonable steps to ensure it complies with (1), (1A) and (1B),  a contravention '
                 'does not give rise to a right of action under section 138D of the Act.',
  'contentType': '<div class="section-content">\n'
                 '<div class="rule">\n'
                 '<ol>\n'
                 '<li class="subpara1" id="D49">\n'
                 '<a name="DES49"></a>(1) <p>A <a class="autodeftext" '
                 'href="/glossary/G430">firm</a> must ensure that a communication or a <a '
                 'class="autodeftext" href="/glossary/G421">financial promotion</a> is clear, '
                 'fair, and not misleading. </p><p>[<strong>Note</strong>: paragraphs 2.2 of <a '
                 'class="autodeftext" href="/glossary/G3330">ILG</a>, 3.16 of <a '
                 'class="autodeftext" href="/glossary/G3326">DMG</a> and 3.1 of <a '
                 'class="autodeftext" href="/glossary/G3301">CBG</a>]</p></li>\n'
                 '<li class="subpara1" id="D404">\n'
                 '<a name="DES49"></a>(1A) <p>A <a class="autodeftext" '
                 'href="/glossary/G430">firm</a> must ensure that each communication and each <a '
                 'class="autodeftext" href="/glossary/G421">financial promotion</a>:</p><ol><li '
                 'class="subpara2" id="D405"><a name="DES49"></a>(a) <p>is clearly identifiable as '
                 'such;</p></li><li class="subpara2" id="D406"><a name="DES49"></a>(b) <p>is '
                 'accurate;</p></li><li class="subpara2" id="D407"><a name="DES49"></a>(c) <p>is '
                 'balanced and, in particular, does not emphasise any potential benefits of a '
                 'product or service without also giving a fair and prominent indication of any '
                 'relevant risks;</p></li><li class="subpara2" id="D408"><a name="DES49"></a>(d) '
                 '<p>is sufficient for, and presented in a way that is likely to be understood by, '
                 'the average member of the group to which it is directed, or by which it is '
                 'likely to be received; and</p></li><li class="subpara2" id="D409"><a '
                 'name="DES49"></a>(e) <p>does not disguise, omit, diminish or obscure important '
                 'information, statements or warnings.</p></li></ol></li>\n'
                 '<li class="subpara1" id="D410">\n'
                 '<a name="DES49"></a>(1B) <p>A <a class="autodeftext" '
                 'href="/glossary/G430">firm</a> must ensure that, where a communication or <a '
                 'class="autodeftext" href="/glossary/G421">financial promotion</a> contains a '
                 'comparison or contrast, the comparison or contrast is presented in a fair and '
                 'balanced way and is meaningful.</p></li>\n'
                 '<li class="subpara1" id="D50">\n'
                 '<a name="DES50"></a>(2) <p>If, for a particular communication or <a '
                 'class="autodeftext" href="/glossary/G421">financial promotion</a>, a <a '
                 'class="autodeftext" href="/glossary/G430">firm</a> takes reasonable steps to '
                 'ensure it complies with (1), (1A) and (1B), a contravention does not give rise '
                 'to a right of action under <a class="external-link" '
                 'href="https://www.legislation.gov.uk/ukpga/2000/8/section/138D/2014-04-01" '
                 'target="_blank">section 138D</a> of the <a class="autodeftext" '
                 'href="/glossary/G10">Act</a>.</p></li>\n'
                 '</ol>\n'
                 '</div>\n'
                 '</div>',
  'isDeleted': False,
  'provisionName': 'CONC 3.3.1',
  'provisionType': 'Rules',
  'sectionId': 'conc3s3',
  'sectionName': 'CONC 3.3 The clear fair and not misleading rule and general requirements'},
 {'contentText': "(1) A firm's trading name, internet address or logo, in particular, could fall "
                 'within CONC 3.3.3 R. [Note: paragraph 5.2 (box) of ILG]\n'
                 '\n'
                 '(2) A statement or an implication that credit is guaranteed or pre-approved, or '
                 'is not subject to any credit checks or other assessment of creditworthiness, may '
                 'contravene CONC 3.3.3R. Firms are reminded of the requirements of CONC 5 '
                 '(Responsible lending).',
  'contentType': '<div class="section-content">\n'
                 '<div class="guidance">\n'
                 '<ol>\n'
                 '<li class="subpara1" id="D58">\n'
                 '<a name="DES58"></a>(1) <p>A <a class="autodeftext" '
                 'href="/glossary/G430">firm\'s</a> trading name, internet address or logo, in '
                 'particular, could fall within <span class="xref"><span class="xrefin" '
                 'id="SRC14"><a href="/handbook/conc3/conc3s3#p30441">CONC 3.3.3 '
                 'R</a></span></span>. </p><p>[<strong>Note</strong>: paragraph 5.2 (box) of <a '
                 'class="autodeftext" href="/glossary/G3330">ILG</a>]</p></li>\n'
                 '<li class="subpara1" id="D59">\n'
                 '<a name="DES59"></a>(2) <p>A statement or an implication that <a '
                 'class="autodeftext" href="/glossary/G238">credit</a> is guaranteed or '
                 'pre-approved, or is not subject to any <a class="autodeftext" '
                 'href="/glossary/G238">credit</a> checks or other assessment of creditworthiness, '
                 'may contravene <span class="xref"><span class="xrefout"><a '
                 'href="/handbook/conc3/conc3s3#p30441">CONC 3.3.3R</a></span></span>. <a '
                 'class="autodeftext" href="/glossary/G430">Firms</a> are reminded of the '
                 'requirements of <span class="xref"><span class="xrefout" id="SRC68"><a '
                 'href="/handbook/conc5">CONC 5</a></span></span> (Responsible lending).</p></li>\n'
                 '</ol>\n'
                 '</div>\n'
                 '</div>',
  'isDeleted': False,
  'provisionName': 'CONC 3.3.4',
  'provisionType': 'Guidance',
  'sectionId': 'conc3s3',
  'sectionName': 'CONC 3.3 The clear fair and not misleading rule and general requirements'}]

def chunks():
    return chunk_provisions(PROVISIONS, source_url=SOURCE_URL, retrieved_on=RETRIEVED_ON)


def test_one_chunk_per_provision():
    assert len(chunks()) == 2


def test_rule_id_extraction():
    assert [c["rule_id"] for c in chunks()] == ["CONC 3.3.1", "CONC 3.3.4"]


def test_designation():
    assert [c["designation"] for c in chunks()] == ["R", "G"]


def test_metadata_completeness():
    for c in chunks():
        assert set(c) == {"sourcebook", "chapter", "section", "rule_id", "designation",
                          "text", "source_url", "retrieved_on"}
        assert c["sourcebook"] == "CONC"
        assert c["chapter"] == "3"
        assert c["section"] == "CONC 3.3"
        assert c["source_url"] == SOURCE_URL
        assert c["retrieved_on"] == RETRIEVED_ON


def test_text_has_section_title_prefix_and_rule_text():
    rule = chunks()[0]
    lines = rule["text"].splitlines()
    assert lines[0] == "CONC 3.3.1 R"
    assert lines[1] == "CONC 3.3 The clear fair and not misleading rule and general requirements"
    assert "(1) A firm must ensure that a communication or a financial promotion is clear, fair, and not misleading." in rule["text"]
    # nested sub-paragraphs from the HTML keep their own lines (contentText flattens them)
    assert "(a) is clearly identifiable as such;" in lines


def test_deleted_provisions_are_skipped():
    deleted = dict(PROVISIONS[0], isDeleted=True)
    assert chunk_provisions([deleted], source_url=SOURCE_URL, retrieved_on=RETRIEVED_ON) == []


def test_tables_render_one_row_per_line_without_trailing_pipe():
    table = "<table><tr><td>Loan</td><td>Rate</td></tr><tr><td>£100</td><td>5%</td></tr></table>"
    prov = dict(PROVISIONS[0], contentType=table)
    text = chunk_provisions([prov], source_url=SOURCE_URL, retrieved_on=RETRIEVED_ON)[0]["text"]
    assert "Loan | Rate" in text.splitlines()
    assert "£100 | 5%" in text.splitlines()


def test_empty_html_content_raises():
    prov = dict(PROVISIONS[0], contentType="<div></div>")
    with pytest.raises(ValueError, match="CONC 3.3.1"):
        chunk_provisions([prov], source_url=SOURCE_URL, retrieved_on=RETRIEVED_ON)
