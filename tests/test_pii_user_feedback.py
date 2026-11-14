"""三位独立使用者实测反馈（2026-11 半决赛冲刺证据链）PII 脱敏回归。

反馈→修复→回归闭环的硬证据：每条用例对应用户报告的原始样例，
走产品实际路径（sixvolumes.pii.recognize_identifiers → lineage.redact_with_lineage）。
反馈人：Freya0821（3.5/5，脱敏 2 分）、meili-loli（4/5）、Charles236（4.8/5）。
"""
import pytest

from sixvolumes.lineage import redact_with_lineage
from sixvolumes.pii import recognize_identifiers


def hits(text, entity_type):
    return [e for e in recognize_identifiers(text) if e.type == entity_type]


def product_masked(text):
    masked, vault, _, _ = redact_with_lineage(text)
    return masked, vault


class TestDashPhoneFromUserFeedback:
    """缺陷①：横杠手机号漏检（用户原话样例 138-1234-5678；连续与空格形式已可识别）。"""

    @pytest.mark.parametrize(
        "text,phone",
        [
            ("联系电话138-1234-5678请回拨", "138-1234-5678"),
            ("手机 138-1234-5678，谢谢", "138-1234-5678"),
            ("备用号138 1234 5678。", "138 1234 5678"),
            ("全角写法138－1234－5678", "138－1234－5678"),
            ("混合分隔138-1234 5678也可以", "138-1234 5678"),
        ],
    )
    def test_dash_phone_masked_with_lineage_roundtrip(self, text, phone):
        found = hits(text, "PHONE")
        assert found, f"漏检: {text!r}"
        assert found[0].text == phone
        masked, vault = product_masked(text)
        assert phone not in masked
        assert vault.restore(masked) == text

    def test_contiguous_phone_still_detected(self):
        assert [e.text for e in hits("联系电话13812345678请回拨", "PHONE")] == ["13812345678"]

    def test_segment_gate_kept(self):
        assert hits("联系电话140-1234-5678", "PHONE") == []


class TestIdCardXFromUserFeedback:
    """缺陷②：身份证 X 结尾。校验位合法（ISO 7064 MOD 11-2）的各形态应检出；校验门保持。"""

    @pytest.mark.parametrize(
        "value",
        ["11010519491231002X", "11010519491231002x", "11010519491231002Ｘ"],
    )
    def test_valid_x_suffix_masked(self, value):
        text = "身份证号" + value + "，请核对"
        found = hits(text, "ID_CARD")
        assert found and found[0].text == value
        masked, vault = product_masked(text)
        assert value not in masked
        assert vault.restore(masked) == text

    def test_invalid_checksum_x_suffix_still_rejected(self):
        # MOD 11-2 校验位不符的合成号按“宁缺勿滥”设计拒检（校验门即准确率来源）
        assert hits("身份证号12345619500101001X", "ID_CARD") == []
        assert hits("身份证号11010119900307866X", "ID_CARD") == []


class TestWxidFromUserFeedback:
    """缺陷③：wxid_ 前缀微信号漏检（无“微信号”关键词上下文时）。"""

    def test_wxid_without_keyword_masked(self):
        text = "加我wxid_8fjkl12345"
        found = hits(text, "WECHAT_ID")
        assert found and found[0].text == "wxid_8fjkl12345"
        masked, vault = product_masked(text)
        assert "wxid_8fjkl12345" not in masked
        assert vault.restore(masked) == text

    def test_wxid_with_keyword_still_masked(self):
        text = "微信号：wxid_8fjkl12345"
        assert [e.text for e in hits(text, "WECHAT_ID")] == ["wxid_8fjkl12345"]

    def test_wxid_inside_longer_token_not_matched(self):
        assert hits("代号awxid_8fjkl12345", "WECHAT_ID") == []


class TestAddressSpaceFromUserFeedback:
    """缺陷④：地址含空格漏检。"""

    def test_address_with_spaces_masked(self):
        text = "地址：北京市 朝阳区 建国路 88 号。"
        found = hits(text, "ADDRESS")
        assert found and found[0].text == "北京市 朝阳区 建国路 88 号"
        masked, vault = product_masked(text)
        assert "北京市 朝阳区 建国路 88 号" not in masked
        assert vault.restore(masked) == text

    def test_address_without_spaces_still_masked(self):
        text = "地址：北京市朝阳区建国路88号。"
        assert [e.text for e in hits(text, "ADDRESS")] == ["北京市朝阳区建国路88号"]


class TestLocalPathFromUserFeedback:
    """缺陷⑤：本地路径（如 C:\\Users\\name\\file.txt）未脱敏。"""

    @pytest.mark.parametrize(
        "text,path",
        [
            ("配置文件在C:\\Users\\zhangsan\\AppData\\config.txt里", "C:\\Users\\zhangsan\\AppData\\config.txt"),
            ("日志位于D:/data/backup/user_info.xlsx。", "D:/data/backup/user_info.xlsx"),
            ("配置见/etc/nginx/nginx.conf，请检查。", "/etc/nginx/nginx.conf"),
            ("共享盘\\\\fileserver\\docs\\合同2026.docx已收到", "\\\\fileserver\\docs\\合同2026.docx"),
        ],
    )
    def test_local_path_masked_with_lineage_roundtrip(self, text, path):
        found = hits(text, "FILE_PATH")
        assert found, f"漏检: {text!r}"
        assert found[0].text == path
        masked, vault = product_masked(text)
        assert path not in masked
        assert vault.restore(masked) == text

    def test_url_kept_whole_not_split(self):
        text = "官网 https://example.com/docs/README.md 已更新"
        types = [(e.type, e.text) for e in recognize_identifiers(text)]
        assert types == [("URL", "https://example.com/docs/README.md")]

    def test_plain_sentence_not_path(self):
        assert recognize_identifiers("比例3:1/2和A:B/2都不该算路径") == []


class TestSeniorEngineerFromUserFeedback:
    """缺陷⑥：“高级工程师”被称谓线索误判为人名“高级”（误报）。"""

    def test_not_flagged_as_person(self):
        text = "他是一名高级工程师。"
        assert hits(text, "PERSON_NAME") == []
        masked, vault = product_masked(text)
        assert masked == text  # 无人名替换，原文原样保留

    def test_real_name_before_engineer_still_detected(self):
        text = "今天张伟明工程师来访。"
        assert [e.text for e in hits(text, "PERSON_NAME")] == ["张伟明"]


def test_all_fixes_keep_offset_and_roundtrip_invariants():
    """六项样例合并走一遍产品路径：span 恒等 + vault 还原闭环。"""
    samples = [
        "联系电话138-1234-5678请回拨",
        "身份证号11010519491231002X，请核对",
        "加我wxid_8fjkl12345",
        "地址：北京市 朝阳区 建国路 88 号。",
        "配置文件在C:\\Users\\zhangsan\\AppData\\config.txt里",
        "他是一名高级工程师。",
    ]
    for text in samples:
        for e in recognize_identifiers(text):
            assert text[e.start:e.end] == e.text
        masked, vault, _, _ = redact_with_lineage(text)
        assert vault.restore(masked) == text
