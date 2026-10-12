import unittest
import xml.etree.ElementTree as ET

from render_profile import START, END, activities_from, render, units, wrap_title


class ProfileTests(unittest.TestCase):
    def test_feed_and_xml_escaping(self):
        entries = activities_from(START + '\n- [看过 A & B <2026>](https://example.com/?a=1&b=2)\n' + END)
        self.assertEqual(entries[0], ('看过', 'A & B <2026>', 'https://example.com/?a=1&b=2'))
        for mobile in (False, True):
            svg = render(entries, mobile, {})
            self.assertIn('A &amp; B &lt;2026&gt;', svg)
            self.assertIsNotNone(ET.fromstring(svg))

    def test_long_titles_fit_and_remain_in_description(self):
        title = '很长的书名' * 50
        lines = wrap_title(title, 26)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith('…'))
        self.assertTrue(all(units(line) <= 26 for line in lines))
        self.assertIn(title, render([('在读', title, 'https://example.com')], True, {}))

    def test_rejects_broken_source_and_limits_entries(self):
        for source in ('no markers', END+START, START+START+END, START+'bad row'+END):
            with self.assertRaises(ValueError):
                activities_from(source)
        source = START+'\n'+('- [读过 Book](https://example.com)\n'*5)+END
        self.assertEqual(len(activities_from(source)), 3)
        self.assertIn('暂无近期书影音记录', render([], True, {}))


if __name__ == '__main__':
    unittest.main()
