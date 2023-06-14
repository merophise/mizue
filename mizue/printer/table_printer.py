import enum
import math
import os
import sys

from wcwidth import wcswidth, wcwidth

from mizue.printer import Printer
from mizue.printer.alignment import Alignment
from mizue.printer.border_style import BorderStyle
from mizue.util import Utility


class TablePrinter:

    def __init__(self, table_data: list[list[str]]):
        if len(table_data) == 0:
            raise ValueError("Table data cannot be empty")

        self._formatted_table_data = []
        self._formatted_title_data = []
        self._ranges = []

        self.align_list = []
        self.auto_width: list[bool] = []
        self.border_color = None
        self.border_style = BorderStyle.BASIC
        self.cell_length_list = []
        self.color_list = []
        self.enumerated = False
        self.enumeration_color = None
        self.enumeration_title = "#"
        self.table_data = table_data
        self.title_data = []

    def print(self):
        """Prints the table to the console"""
        if len(self.table_data) == 0:
            return
        self._initialize()
        buffer = self._buffer_table()
        sys.stdout.flush()
        print(buffer)

    @staticmethod
    def print_text_with_border(text: str, text_color: str = None, border_color: str = None,
                               border_style: BorderStyle = BorderStyle.SINGLE):
        """Prints a single line of text with a border"""
        printer = TablePrinter([[text]])
        printer.color_list = [text_color]
        printer.border_color = border_color
        printer.border_style = border_style
        printer.print()

    def _apply_enumeration(self, has_title: bool = False):
        index = 1
        if has_title:
            header_str = self.enumeration_title if self.enumeration_title else "#"
            self.title_data.insert(0, header_str)
        for row in self.table_data:
            row_number = f"{index}"
            row.insert(0, row_number)
            index += 1

    def _buffer_table(self):
        title_data = self._formatted_title_data
        table_data = self._formatted_table_data
        buffer = [self._create_row_border(RowBorderPosition.TOP), os.linesep]
        if title_data:
            buffer.append(self._create_row(title_data))
            buffer.append(os.linesep)
            buffer.append(self._create_row_border(RowBorderPosition.MIDDLE))
            buffer.append(os.linesep)
        for index, row in enumerate(table_data):
            buffer.append(self._create_row(row))
            buffer.append(os.linesep)
        buffer.append(self._create_row_border(RowBorderPosition.BOTTOM))
        return "".join(buffer)

    def _create_row_border(self, position):
        dash_list = []
        border_style = self._get_border_style()
        if position is RowBorderPosition.TOP:
            left = border_style.TOPLEFT
            middle = border_style.TOPMIDDLE
            right = border_style.TOPRIGHT
        elif position is RowBorderPosition.BOTTOM:
            left = border_style.BOTTOMLEFT
            middle = border_style.BOTTOMMIDDLE
            right = border_style.BOTTOMRIGHT
        elif position is RowBorderPosition.MIDDLE:
            left = border_style.LEFTMIDDLE
            middle = border_style.MIDDLEMIDDLE
            right = border_style.RIGHTMIDDLE
        dash_list.append(left)
        for index, max_length in enumerate(self.cell_length_list):
            dash_list.append("".join([border_style.HORIZONTAL] * (max_length + 2)))
            if index != len(self.cell_length_list) - 1:
                dash_list.append(middle)
        dash_list.append(right)
        return Printer.format_hex("".join(dash_list), self.border_color) if self.border_color else "".join(dash_list)

    def _create_row(self, row: list):
        row_list = []
        border_style = self._get_border_style()
        for index, cell in enumerate(row):
            border = Printer.format_hex(border_style.VERTICAL,
                                        self.border_color) if self.border_color else border_style.VERTICAL
            row_list.append(str.format("{}{}", border, " "))
            if self.align_list[index] is Alignment.RIGHT:
                cell_length = self._get_terminal_length(Printer.strip_ansi(cell))
                row_list.append("".join([" "] * (self.cell_length_list[index] - cell_length)))
            elif self.align_list[index] is Alignment.CENTER:
                cell_length = self._get_terminal_length(Printer.strip_ansi(cell))
                length = self.cell_length_list[index]
                txt = "".join([" "] * (int(math.floor((length - cell_length) / 2))))
                row_list.append(txt)

            if index == 0 and self.enumerated:
                cell_color = self.enumeration_color
            else:
                cell_color = self.color_list[index] if self.color_list and self.color_list[index] else None

            colored_text = ""
            if isinstance(cell_color, tuple):
                colored_text = Printer.format_rgb(cell, cell_color)
            elif isinstance(cell_color, str):
                colored_text = Printer.format_hex(cell, cell_color) if cell_color.startswith(
                    "#") else Printer.format(cell, cell_color)
            elif cell_color is None:
                colored_text = cell
            cell_format = colored_text

            row_list.append(cell_format)
            if self.align_list[index] is Alignment.LEFT:
                cell_length = self._get_terminal_length(Printer.strip_ansi(cell_format))
                row_list.append("".join([" "] * (self.cell_length_list[index] - cell_length)))
            elif self.align_list[index] is Alignment.CENTER:
                cell_length = self._get_terminal_length(Printer.strip_ansi(cell_format))
                length = self.cell_length_list[index]
                txt = "".join([" "] * (int(math.ceil((length - cell_length) / 2))))
                row_list.append(txt)

            row_list.append(" ")
        border = Printer.format_hex(border_style.VERTICAL,
                                    self.border_color) if self.border_color else border_style.VERTICAL
        row_list.append(border)
        return "".join(row_list)

    def _get_border_style(self):
        if self.border_style == BorderStyle.SINGLE:
            return BorderCharacterCodes.Single
        if self.border_style == BorderStyle.DOUBLE:
            return BorderCharacterCodes.Double
        if self.border_style == BorderStyle.BASIC:
            return BorderCharacterCodes.Basic
        if self.border_style == BorderStyle.EMPTY:
            return BorderCharacterCodes.Empty
        return BorderCharacterCodes.Basic

    @staticmethod
    def _find_max_cell_length(row_data: list):
        max_length_list = [0] * len(row_data[0])
        cell_index = 0
        for row in row_data:
            for cell in row:
                max_length_list[cell_index] = max(len(cell), max_length_list[cell_index])
                cell_index += 1
            cell_index = 0
        return max_length_list

    def _find_max_column_cell_length(self, col_data: list):
        max_length = -1
        for row_index, col_row in enumerate(col_data):
            length = 0
            stripped_col_row = Printer.strip_ansi(str(col_row))
            for ch in stripped_col_row:
                if self._is_long_terminal_char(ch):
                    length += 2
                else:
                    length += 1
            length = length + 1 if TablePrinter._has_variation_selector(stripped_col_row) else length
            max_length = max(max_length, length)
        return max_length

    def _format_long_cells(self):
        formatted_data = []
        temp_data: list = self.table_data.copy()
        if len(self.title_data) > 0:
            temp_data.insert(0, self.title_data)
        for row in temp_data:
            formatted_row = []
            for col_index, cell_data in enumerate(row):
                cell = str(cell_data)
                terminal_length = self._get_terminal_length(cell)
                cell_length = self.cell_length_list[col_index]
                remaining_chars = Printer.strip_ansi(cell[0:cell_length - 3])

                remaining_chars_normal_length = len(remaining_chars)
                remaining_chars_terminal_length = self._get_terminal_length(remaining_chars)

                if remaining_chars_terminal_length != remaining_chars_normal_length:
                    if remaining_chars_terminal_length - 3 < cell_length:
                        visible_length = remaining_chars_terminal_length - 3 - sum(
                            [2 if wcwidth(c) == 2 else 0 for c in remaining_chars])
                    else:
                        diff = remaining_chars_terminal_length - remaining_chars_normal_length
                        visible_length = cell_length - diff - 3
                else:
                    visible_length = cell_length - 3

                if not self._auto_width[col_index]:
                    if cell_length > 3:
                        formatted_cell = cell[:visible_length] + "..." if terminal_length > cell_length else cell
                    else:
                        formatted_cell = "".join(["." for _ in range(cell_length)])
                    formatted_row.append(formatted_cell)
                else:
                    if terminal_length > cell_length:
                        formatted_row.append(cell[:visible_length] + "...")
                    else:
                        formatted_row.append(str(cell))
            formatted_data.append(formatted_row)

        if len(self.title_data) > 0:
            self._formatted_title_data = formatted_data[0]
            self._formatted_table_data = formatted_data[1:]
        else:
            self._formatted_table_data = formatted_data

    def _get_auto_column_cell_lengths(self):
        temp_data: list = self.table_data.copy()
        if len(self.title_data) > 0:
            temp_data.insert(0, self.title_data)
        max_lengths_list = []
        for index in range(0, len(temp_data[0])):
            column = [item[index] for item in temp_data]
            max_length = self._find_max_column_cell_length(column)
            max_lengths_list.append(max_length)
        max_lengths = len(self.cell_length_list)
        for index, length in enumerate(max_lengths_list):
            if index < max_lengths and (self.cell_length_list[index] is None or self.cell_length_list[index] == 0):
                self.cell_length_list[index] = length
        self._resize_columns_to_fit()
        return self.cell_length_list

    @staticmethod
    def _get_terminal_length(text: str) -> int:
        length = sum([2 if wcwidth(c) == 2 else 1 for c in text])
        return length

    @staticmethod
    def _has_variation_selector(text: str) -> bool:
        return any(TablePrinter._is_variation_selector(c) for c in text)

    def _initialize(self):
        if self.enumerated:
            self._apply_enumeration(len(self.title_data) > 0)
        offset = 1 if self.enumerated else 0
        self.cell_length_list += [None] * (len(self.table_data[0]) - offset - len(self.cell_length_list))
        if self.enumerated:
            self.cell_length_list.insert(0, None)
        self._auto_width = [True if max_length is None or max_length == 0 else False for max_length in
                            self.cell_length_list]
        # if self.enumerated:
        #     self._auto_width.insert(0, True)
        if self.title_data and len(self.title_data) < len(self.table_data[0]):
            self.title_data += [""] * (len(self.table_data[0]) - len(self.title_data))

        self.cell_length_list = self._get_auto_column_cell_lengths()

        if len(self.cell_length_list) > len(self.table_data[0]):
            self.cell_length_list = self.cell_length_list[:len(self.table_data[0])]

        self.color_list += [None] * (len(self.table_data[0]) - offset - len(self.color_list))
        if self.enumerated:
            self.color_list.insert(0, None)

        self.align_list += [Alignment.LEFT] * (len(self.table_data[0]) - offset - len(self.align_list))
        if self.enumerated:
            self.align_list.insert(0, Alignment.RIGHT)

        self._format_long_cells()

    def _init_unicode_ranges(self):
        self._ranges = [
            {"from": ord(u"\u3300"), "to": ord(u"\u33ff")},  # compatibility ideographs
            {"from": ord(u"\ufe30"), "to": ord(u"\ufe4f")},  # compatibility ideographs
            {"from": ord(u"\uf900"), "to": ord(u"\ufaff")},  # compatibility ideographs
            {"from": ord(u"\U0002F800"), "to": ord(u"\U0002fa1f")},  # compatibility ideographs
            {"from": ord(u'\u3000'), "to": ord(u'\u303F')},  # Japanese Punctuation
            {'from': ord(u'\u3040'), 'to': ord(u'\u309f')},  # Japanese Hiragana
            {"from": ord(u"\u30a0"), "to": ord(u"\u30ff")},  # Japanese Katakana
            {"from": ord(u"\u2e80"), "to": ord(u"\u2eff")},  # cjk radicals supplement
            {"from": ord(u"\u4e00"), "to": ord(u"\u9fff")},
            {"from": ord(u"\u3400"), "to": ord(u"\u4dbf")},
            {"from": ord(u"\uac00"), "to": ord(u"\ud7af")},  # hangul syllables
            {"from": ord(u"\uff00"), "to": ord(u"\uffef")},  # full width unicode chars
            {"from": ord(u"\U00020000"), "to": ord(u"\U0002a6df")},
            {"from": ord(u"\U0002a700"), "to": ord(u"\U0002b73f")},
            {"from": ord(u"\U0002b740"), "to": ord(u"\U0002b81f")},
            {"from": ord(u"\U0002b820"), "to": ord(u"\U0002ceaf")}  # included as of Unicode 8.0
        ]

    def _is_cjk(self, char):  # CJK: Chinese, Japanese, Korean
        return any([r["from"] <= ord(char) <= r["to"] for r in self._ranges])

    def _is_half_width_cjk(self, char):
        return self._is_cjk(char) and (0xff61 <= ord(char) <= 0xff9f)

    @staticmethod
    def _is_long_terminal_char(char):
        return wcswidth(char) == 2
        # return self._is_cjk(char) or self._is_long_unicode(char)

    def _is_long_unicode(self, char):
        return not self._is_cjk(char) and ord(char) > 65536

    @staticmethod
    def _is_variation_selector(char):
        return 0xfe00 <= ord(char) <= 0xfe0f

    def _resize_columns_to_fit(self):
        terminal_length = Utility.get_terminal_width()
        total_length = sum([x for x in self.cell_length_list if x is not None]) + (len(self.cell_length_list) * 3) + 1
        new_length = int(terminal_length / len(self.cell_length_list))
        short_columns = [x for x in self.cell_length_list if x is not None and x < new_length]
        long_columns = [x for x in self.cell_length_list if x is not None and x > new_length]
        remaining_length = terminal_length - (new_length * len(short_columns) if len(short_columns) > 0 else 0)
        padding_length = int(math.floor(remaining_length / len(long_columns))) if len(long_columns) > 0 else 0

        if total_length > terminal_length:
            for cx in range(1, len(self.cell_length_list)):
                if self.cell_length_list[cx] is not None:
                    self.cell_length_list[cx] = self.cell_length_list[cx] \
                        if self.cell_length_list[cx] < new_length else new_length + padding_length


class BorderCharacterCodes:
    class Double:
        TOPLEFT = u'\u2554'  # 0xC9 -> BOX DRAWINGS DOUBLE DOWN AND RIGHT
        TOPRIGHT = u'\u2557'  # 0xBB -> BOX DRAWINGS DOUBLE DOWN AND LEFT
        BOTTOMLEFT = u'\u255a'  # 0xC8 -> BOX DRAWINGS DOUBLE UP AND RIGHT
        BOTTOMRIGHT = u'\u255d'  # 0xBC -> BOX DRAWINGS DOUBLE UP AND LEFT
        TOPMIDDLE = u'\u2566'  # 0xCB -> BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        BOTTOMMIDDLE = u'\u2569'  # 0xCA -> BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        LEFTMIDDLE = u'\u2560'  # 0xCC -> BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        RIGHTMIDDLE = u'\u2563'  # 0xB9 -> BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        MIDDLEMIDDLE = u'\u256c'  # 0xCE -> BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        HORIZONTAL = u'\u2550'  # 0xCD -> BOX DRAWINGS DOUBLE HORIZONTAL
        VERTICAL = u'\u2551'  # 0xBA -> BOX DRAWINGS DOUBLE VERTICAL

    class Single:
        TOPLEFT = u'\u250c'  # 0xDA -> BOX DRAWINGS LIGHT DOWN AND RIGHT
        TOPRIGHT = u'\u2510'  # 0xBF -> BOX DRAWINGS LIGHT DOWN AND LEFT
        BOTTOMLEFT = u'\u2514'  # 0xC0 -> BOX DRAWINGS LIGHT UP AND RIGHT
        BOTTOMRIGHT = u'\u2518'  # 0xD9 -> BOX DRAWINGS LIGHT UP AND LEFT
        TOPMIDDLE = u'\u252c'  # 0xC2 -> BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        BOTTOMMIDDLE = u'\u2534'  # 0xC1 -> BOX DRAWINGS LIGHT UP AND HORIZONTAL
        LEFTMIDDLE = u'\u251c'  # 0xC3 -> BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        RIGHTMIDDLE = u'\u2524'  # 0xB4 -> BOX DRAWINGS LIGHT VERTICAL AND LEFT
        MIDDLEMIDDLE = u'\u253c'  # 0xC5 -> BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        HORIZONTAL = u'\u2500'  # 0xC4 -> BOX DRAWINGS LIGHT HORIZONTAL
        VERTICAL = u'\u2502'  # 0xB3 -> BOX DRAWINGS LIGHT VERTICAL

    class Basic:
        TOPLEFT = "+"
        TOPRIGHT = "+"
        BOTTOMLEFT = "+"
        BOTTOMRIGHT = "+"
        TOPMIDDLE = "+"
        BOTTOMMIDDLE = "+"
        LEFTMIDDLE = "+"
        RIGHTMIDDLE = "+"
        MIDDLEMIDDLE = "+"
        HORIZONTAL = "-"
        VERTICAL = "|"

    class Empty:
        TOPLEFT = ""
        TOPRIGHT = ""
        BOTTOMLEFT = ""
        BOTTOMRIGHT = ""
        TOPMIDDLE = ""
        BOTTOMMIDDLE = ""
        LEFTMIDDLE = ""
        RIGHTMIDDLE = ""
        MIDDLEMIDDLE = ""
        HORIZONTAL = ""
        VERTICAL = ""

class RowBorderPosition(enum.Enum):
    TOP = 1,
    MIDDLE = 2,
    BOTTOM = 3