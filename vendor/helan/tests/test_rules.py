"""规则类 recognizer 测试。"""

from __future__ import annotations

from helan.recognizers.rules import (
    recognize_email,
    recognize_file_path,
    recognize_ip,
    recognize_landline,
    recognize_passport,
    recognize_plate,
    recognize_url,
)


class TestEmail:
    def test_simple(self):
        ents = recognize_email("邮箱 user.ming@example.cn 结束")
        assert len(ents) == 1
        assert ents[0].text == "user.ming@example.cn"

    def test_multi_level_domain(self):
        assert recognize_email("a@mail.example.com.cn")[0].end - recognize_email("a@mail.example.com.cn")[0].start == 21

    def test_rejects_leading_dot(self):
        assert recognize_email(".user@example.com") == []

    def test_no_false_in_text(self):
        assert recognize_email("没有邮箱的文本") == []


class TestIp:
    def test_valid(self):
        ents = recognize_ip("服务器 IP 是 192.168.1.100。")
        assert ents[0].text == "192.168.1.100"

    def test_octet_range(self):
        assert recognize_ip("256.1.1.1") == []
        assert recognize_ip("10.0.0.999") == []

    def test_guard_inside_digits(self):
        assert recognize_ip("版本号12.168.1.2345") == []

    def test_trailing_dot_allowed(self):
        ents = recognize_ip("IP:10.0.0.1.")
        assert ents[0].text == "10.0.0.1"


class TestUrl:
    def test_basic(self):
        ents = recognize_url("详见 https://example.com/a/b?x=1 说明")
        assert ents[0].text == "https://example.com/a/b?x=1"

    def test_chinese_trailing_punct_trimmed(self):
        ents = recognize_url("打开 https://example.com/x。")
        assert ents[0].text.endswith("x")
        assert ents[0].meta["trimmed_len"] == len("https://example.com/x")


class TestLandline:
    def test_valid_area(self):
        ents = recognize_landline("电话 010-65542317。")
        assert ents[0].text == "010-65542317"

    def test_no_dash(self):
        assert recognize_landline("电话 02163321588。")[0].text == "02163321588"

    def test_unknown_area_rejected(self):
        assert recognize_landline("电话 099-1234567") == []


class TestPlate:
    def test_standard(self):
        ents = recognize_plate("车牌 京AD1289 停放")
        assert ents[0].text == "京AD1289"

    def test_with_dot(self):
        assert recognize_plate("车牌 京A·D1289 停放")[0].text == "京A·D1289"

    def test_new_energy_six(self):
        assert recognize_plate("新能源 沪BD12345")[0].text == "沪BD12345"

    def test_i_o_excluded(self):
        assert recognize_plate("车牌 京AI1234") == []


class TestPassport:
    def test_valid(self):
        ents = recognize_passport("护照号 E12345678。")
        assert ents[0].text == "E12345678"

    def test_guarded(self):
        assert recognize_passport("编号XE1234567890") == []

    def test_short_rejected(self):
        assert recognize_passport("E1234567") == []


class TestFilePathFromUserFeedback:
    def test_windows_backslash_path(self):
        # 用户反馈漏检样例：C:\Users\name\file.txt 未脱敏
        ents = recognize_file_path("配置文件在C:\\Users\\zhangsan\\AppData\\config.txt里")
        assert len(ents) == 1
        assert ents[0].text == "C:\\Users\\zhangsan\\AppData\\config.txt"
        assert ents[0].type == "FILE_PATH"

    def test_forward_slash_path_with_trailing_punct(self):
        ents = recognize_file_path("日志位于D:/data/backup/user_info.xlsx。")
        assert len(ents) == 1
        assert ents[0].text == "D:/data/backup/user_info.xlsx"

    def test_unix_absolute_path(self):
        ents = recognize_file_path("配置见/etc/nginx/nginx.conf，请检查。")
        assert ents[0].text == "/etc/nginx/nginx.conf"

    def test_unc_path(self):
        ents = recognize_file_path("共享盘\\\\fileserver\\docs\\合同2026.docx已收到")
        assert ents[0].text == "\\\\fileserver\\docs\\合同2026.docx"

    def test_path_with_spaces_in_components(self):
        ents = recognize_file_path("安装在C:\\Program Files (x86)\\app\\run.exe目录")
        assert ents[0].text == "C:\\Program Files (x86)\\app\\run.exe"

    def test_chinese_components_with_extension(self):
        ents = recognize_file_path("材料在D:\\资料\\合同.docx。")
        assert ents[0].text == "D:\\资料\\合同.docx"

    def test_plain_sentence_not_path(self):
        # 无扩展名/无盘符的普通句子不误报
        assert recognize_file_path("比例3:1/2和A:B/2都不该算路径") == []
        assert recognize_file_path("没有路径的普通文本。") == []

    def test_bare_drive_not_path(self):
        assert recognize_file_path("盘符是C:后面没有内容") == []

    def test_url_keeps_priority_over_path(self):
        ents = recognize_file_path("官网 https://example.com/docs/README.md 已更新")
        # URL recognizer 负责整段 URL；FILE_PATH 不在 URL 内部切出
        assert all(not e.text.startswith("/") for e in ents)
