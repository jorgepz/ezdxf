#  Copyright (c) 2021, Manfred Moitzi
#  License: MIT License
from typing import Sequence, Iterable, Optional, Tuple, List, Union
import abc
import enum
from ezdxf.math import Matrix44

"""

Text Layout Engine
==================

The main goal of this text layout engine is to layout words as boxes in 
columns, paragraphs, and (bullet) lists. 

The starting point is a layout engine for MTEXT, which can be used for 
different purposes like the drawing add-on or exploding MTEXT into DXF 
primitives. But the engine is not bound to the MTEXT entity, the MTEXT 
entity just defines the basic requirements.

This engine works on given boxes as input and does not render the letter 
shapes by itself, therefore individual kerning between letters is not 
supported in anyway.

Each input box can have an individual rendering object attached, derived from 
the :class:`ContentRenderer` class, which requires two methods:

1. method :meth:`render` to render the box content like the text or the 
   container background

2. method :meth:`line` to render simple straight lines like under- and over 
   stroke lines or fraction dividers.

Content organization
--------------------

The content is divided into containers (layout, column, paragraphs, ...) and
simple boxes for the actual content as cells like words and glue cells like 
spaces or tabs.

Containers
----------

All containers support margins.

1. Layout

    Contains only columns. The size of the layout is determined by the 
    columns inside of the layout. Each column can have a different width.
    
2. Column
    
    Contains only paragraphs. A Column has a fixed width, the height can be
    fixed (MTEXT) or flexible.
    
3. Paragraph

    A paragraph has a fixed width and the height is always flexible.
    A paragraph can contain anything except the high level containers
    Layout and Column.
    
    3.1 FlowText, supports left, right, center and justified alignments;
        indentation for the left side, the right side and the first line; 
        line spacing; no nested paragraphs or bullet lists;
        The final content is distributed as lines separated by "leading" boxes 
        as spacers.
        
    3.2 BulletList, the "bullet" can be any text cell, the flow text of each
        list is an paragraph with left aligned text ...

4. Line
    
    A line contains only simple boxes. A line has a fixed width and the height 
    is defined by the tallest box (+margins) inside the line container. 
    The content cells (words) are connected by glue cells.

Simple Boxes
------------

Do not support margins.

1. Glue cells

    The height of glue cells is always 0.

    1.1 Space, flexible width but has a minimum width, possible line break
    1.2 Non breaking space, like a space but prevents line break between 
        adjacent text cells
    1.3 Soft hyphen, possible line break between adjacent text cells (ignored)
    1.4 Tabulator (treated as space) 

2. Content cells

    2.1 Text cell - the height of a text cell is the cap height (height of 
        letter "X"), ascenders and descenders are ignored. 
        This is not a clipping box, the associated render object can still draw 
        outside of the box borders, this box is only used to determine the final 
        layout location.
        
    2.2 Fraction cell ... (MTEXT!)

3. Leading

    Line separator, the width is always 0.

"""


class ContentRenderer(abc.ABC):
    @abc.abstractmethod
    def render(self, left: float, bottom: float, right: float,
               top: float, m: Matrix44 = None):
        """ Render content into the given borders (lower left and upper right
        corners).

        Args:
            left: x coordinate of the left border
            bottom: y coordinate of the bottom border
            right: x coordinate of the right border
            top: y coordinate of the top border
            m: transformation Matrix44

        """
        pass

    @abc.abstractmethod
    def line(self, x1: float, y1: float, x2: float, y2: float,
             m: Matrix44 = None):
        """ Draw a line from (x1, y1) to (x2, y2). """
        pass


Tuple4f = Tuple[float, float, float, float]
Tuple2f = Tuple[float, float]


def resolve_margins(margins: Optional[Sequence[float]]) -> Tuple4f:
    """ Returns the box margins in CSS like order: top, right, bottom, left.
    """
    if margins is None:
        return 0, 0, 0, 0
    count = len(margins)
    if count == 4:  # CSS: top, right, bottom, left
        return margins[0], margins[1], margins[2], margins[3]
    elif count == 3:  # CSS: top, right, bottom, left=right
        return margins[0], margins[1], margins[2], margins[1]
    elif count == 2:  # CSS: top, right, bottom=top, left=right
        return margins[0], margins[1], margins[0], margins[1]
    elif count == 1:  # CSS: top, right=top, bottom=top, left=top
        return margins[0], margins[0], margins[0], margins[0]


def insert_location(align: int, width: float, height: float) -> Tuple2f:
    """ Returns the left top corner adjusted to the given alignment.
    """
    left = 0
    top = 0
    center = width / 2
    middle = height / 2
    if align == 1:
        pass
    elif align == 2:
        left, top = (-center, 0)
    elif align == 3:
        left, top = (-width, 0)
    elif align == 4:
        left, top = (0, middle)
    elif align == 5:
        left, top = (-center, middle)
    elif align == 6:
        left, top = (-width, middle)
    elif align == 7:
        left, top = (0, height)
    elif align == 8:
        left, top = (-center, height)
    elif align == 9:
        left, top = (-width, height)
    return left, top


class Box(abc.ABC):

    @property
    @abc.abstractmethod
    def total_width(self) -> float:
        pass

    @property
    @abc.abstractmethod
    def total_height(self) -> float:
        pass


class RenderBox(Box):
    @abc.abstractmethod
    def place(self, x: float, y: float):
        """ (x, y) is the top/left corner """
        pass

    @abc.abstractmethod
    def final_location(self) -> Tuple[float, float]:
        """ Returns the final location as the top/left corner """
        pass

    @abc.abstractmethod
    def render(self, m: Matrix44 = None) -> Iterable:
        """ Render content at the final location. """
        pass


class Cell(Box):
    is_visible = False


class Glue(Cell):  # ABC
    EMPTY = tuple()

    def __init__(self, width: float = 0, min_width: float = 0):
        self._min_width: float = min_width
        self._width: float = 0
        self.resize(width)

    def resize(self, width: float):
        self._width = max(width, self._min_width)

    @property
    def total_width(self) -> float:
        return self._width

    @property
    def total_height(self) -> float:
        return 0

    def can_break(self) -> bool:
        return True


class Space(Glue):
    pass


class SoftHyphen(Glue):
    pass


class NonBreakingSpace(Glue):
    def can_break(self) -> bool:
        return False

    def to_space(self) -> Space:
        return Space(self._width, self._min_width)


class Tab(Glue):
    pass


class ContentCell(Cell):  # ABC
    is_visible = True

    def __init__(self, width: float,
                 height: float,
                 renderer: ContentRenderer):
        self._final_x = None
        self._final_y = None
        self._width = width
        self._height = height
        self._renderer = renderer

    def set_final_location(self, x: float, y: float):
        self._final_x = x
        self._final_y = y

    def final_location(self):
        return self._final_x, self._final_y

    @property
    def total_width(self) -> float:
        return self._width

    @property
    def total_height(self) -> float:
        return self._height

    def place(self, x: float, y: float):
        self._final_x = x
        self._final_y = y

    def render(self, x: float = 0, y: float = 0,
               m: Matrix44 = None) -> Iterable:
        """ (x, y) is the top/left corner """
        yield from self._renderer.render(
            left=x, bottom=y - self.total_height,
            right=x + self.total_width, top=y, m=m)


class Text(ContentCell):
    pass


class Fraction(ContentCell):
    pass


_content = {Text, Fraction}
_glue = {Space, NonBreakingSpace, SoftHyphen, Tab}


def normalize_cells(cells: Iterable[Cell]) -> List[Cell]:
    def peek():
        try:
            return type(cells[index + 1])
        except IndexError:
            return None

    content = []
    cells = list(cells)
    prev = None
    for index, cell in enumerate(cells):
        current = type(cell)
        if current in _content:
            if prev in _content:
                raise ValueError('no glue between content cells')
        else:
            if current is SoftHyphen:
                if prev is SoftHyphen:
                    # merge multiple soft hyphens
                    continue
                if prev not in _content or peek() not in _content:
                    # remove soft hyphen without adjacent content
                    continue
        prev = current
        content.append(cell)

    # remove pending glue:
    while content and (type(content[-1]) in _glue):
        content.pop()

    return content


class Container(RenderBox):
    def __init__(self, width: float,
                 height: float = None,
                 margins: Sequence[float] = None,
                 render: ContentRenderer = None):
        self._final_x = None
        self._final_y = None

        # content total_width is None for: defined by content
        self._content_width = width

        # content height is None for: defined by content
        self._content_height = height

        # margins are always defined
        self._margins = resolve_margins(margins)

        # content renderer is optional:
        self._render: Optional = render

    def place(self, x: float, y: float):
        self._final_x = x
        self._final_y = y
        self.place_content()

    def final_location(self):
        if not self.is_placed():
            raise ValueError('Container is not placed.')
        return self._final_x, self._final_y

    def is_placed(self) -> bool:
        return self._final_x is not None and self._final_y is not None

    @abc.abstractmethod
    def __iter__(self) -> RenderBox:
        pass

    @property
    def top_margin(self) -> float:
        return self._margins[0]

    @property
    def right_margin(self) -> float:
        return self._margins[1]

    @property
    def bottom_margin(self) -> float:
        return self._margins[2]

    @property
    def left_margin(self) -> float:
        return self._margins[3]

    @property
    def content_width(self) -> float:
        if self._content_width is None:
            return 0
        else:
            return self._content_width

    @property
    def total_width(self) -> float:
        return self.content_width + self.right_margin + self.left_margin

    @property
    def content_height(self) -> float:
        if self._content_height is None:
            return 0
        else:
            return self._content_height

    @property
    def has_flex_height(self):
        return self._content_height is None

    @property
    def total_height(self) -> float:
        return self.content_height + self.top_margin + self.bottom_margin

    def render(self, m: Matrix44 = None) -> Iterable:
        """ Render container content.

        (x, y) is the top/left corner
        """
        if not self.is_placed():
            raise ValueError('Layout has to be placed before rendering')

        if self._render:
            yield self.render_background(m)
        self.place_content()
        yield from self.render_content(m)

    @abc.abstractmethod
    def place_content(self):
        """ Place container content at the final location. """
        pass

    def render_content(self, m: Matrix44 = None) -> Iterable:
        """ Render content at the final location. """
        for entity in self:
            yield from entity.render(m)

    def render_background(self, m: Matrix44):
        """ Render background at the final location. """
        # Render content background inclusive margins!
        # (x, y) is the top/left corner
        x, y = self.final_location()
        if self._render:
            return self._render.render(
                left=x, bottom=y - self.total_height,
                top=y, right=x + self.total_width, m=m)
        return None


class Line(Container):
    def __init__(self, width: float,
                 align: int = 0,
                 margins: Sequence[float] = None,
                 render: ContentRenderer = None):
        super().__init__(width, None, margins, render)
        self._align = align
        self._cells: List[Cell] = []

    def __iter__(self):
        return iter(self._cells)


class Paragraph(Container):  # ABC
    @abc.abstractmethod
    def distribute_content(self, height: float = None):
        pass


class FlowText(Paragraph):
    """ Single paragraph of flow text.

    Supported paragraph alignments:

        === =================
        0   default
        1   left
        2   right
        3   center
        4   justified
        === =================

    """

    def __init__(self, width: float,
                 align: int = 0,
                 indent: Tuple[float, float, float] = (0, 0, 0),
                 line_spacing: float = 1,
                 tab_stops: Sequence[float] = None,
                 margins: Sequence[float] = None,
                 render: ContentRenderer = None):
        super().__init__(width, None, margins, render)
        self._align = int(align)
        if not (0 <= self._align < 5):
            raise ValueError("invalid paragraph alignment (0-4)")
        first, left, right = indent
        self._indent_first = first
        self._indent_left = left
        self._indent_right = right
        self._line_spacing = line_spacing
        self.tab_stops = list(tab_stops) if tab_stops else []

        # contains the raw and not distributed content:
        self._cells: List[Box] = []

        # contains the final distributed content:
        self._lines: List[Line] = []

    def __iter__(self):
        return iter(self._lines)

    def place_content(self):
        x, y = self.final_location()
        x += self.left_margin
        y -= self.top_margin
        for line in self._lines:
            line.place(x, y)
            y -= line.total_height

    def distribute_content(self, height: float = None):
        """ Distribute the raw content into lines.

        Args:
            height: available total height (margins + content), ``None`` for
                unrestricted paragraph height

        """
        # Create final content as Lines objects

        pass

    def append_content(self, content: Iterable[Box]):
        self._cells.extend(content)


class BulletList(Paragraph):
    pass


class Column(Container):
    def __init__(self, width: float,
                 height: float = None,
                 gutter: float = 0,
                 margins: Sequence[float] = None,
                 render: ContentRenderer = None):
        super().__init__(width, height, margins, render)
        # spacing between columns
        self._gutter = gutter
        self._paragraphs: List[Paragraph] = []

    def clone_empty(self) -> 'Column':
        return self.__class__(
            width=self.content_width,
            height=self.content_height,
            gutter=self.gutter,
            margins=(self.top_margin, self.right_margin,
                     self.bottom_margin, self.left_margin),
            render=self._render
        )

    def __iter__(self):
        return iter(self._paragraphs)

    @property
    def content_height(self) -> float:
        """ Returns the current content height for flexible columns and the
        max. content height otherwise.
        """
        max_height = self.max_content_height
        if max_height is None:
            return self.used_content_height()
        else:
            return max_height

    def used_content_height(self) -> float:
        return sum(p.total_height for p in self._paragraphs)

    @property
    def gutter(self):
        return self._gutter

    @property
    def max_content_height(self) -> Optional[float]:
        return self._content_height

    @property
    def has_free_space(self) -> bool:
        if self.max_content_height is None:  # flexible height column
            return True
        return self.used_content_height() < self.max_content_height

    def place_content(self):
        x, y = self.final_location()
        x += self.left_margin
        y -= self.top_margin
        for p in self._paragraphs:
            p.place(x, y)
            y -= p.total_height

    def append_paragraphs(
            self, paragraphs: Iterable[Paragraph]) -> List[Paragraph]:
        remainer = []
        if self.has_flex_height:
            self._paragraphs.extend(p.freeze() for p in paragraphs)
        else:
            pass
        return remainer


class Layout(Container):
    def __init__(self, width: float,
                 height: float = None,
                 margins: Sequence[float] = None,
                 render: ContentRenderer = None):
        super().__init__(width, height, margins, render)
        self._reference_column_width = width
        self._current_column = 0
        self._columns: List[Column] = []

    def __iter__(self):
        return iter(self._columns)

    @property
    def content_width(self):
        width = self._content_width
        if self._columns:
            width = self._calculate_content_width()
        return width

    def _calculate_content_width(self) -> float:
        width = sum(c.total_width + c.gutter for c in self._columns[:-1])
        if self._columns:
            width += self._columns[-1].total_width
        return width

    @property
    def content_height(self):
        height = self._content_height
        if self._columns:
            height = self._calculate_content_height()
        elif height is None:
            height = 0
        return height

    def _calculate_content_height(self) -> float:
        return max(c.total_height for c in self._columns)

    def place(self, x: float = 0, y: float = 0, align: int = 1):
        """ Place layout at the final location, relative to the insertion
        point (x, y) by the alignment defined by the argument `align`.

        === ================
        1   Top left
        2   Top center
        3   Top right
        4   Middle left
        5   Middle center
        6   Middle right
        7   Bottom left
        8   Bottom center
        9   Bottom right
        === ================

        """

        width = self.total_width
        height = self.total_height
        left, top = insert_location(align, width, height)
        super().place(x + left, y + top)

    def place_content(self):
        """ Place content at the final location. """
        x, y = self.final_location()
        x = x + self.left_margin
        y = y - self.top_margin
        for column in self:
            column.place(x, y)
            x += column.total_width + column.gutter

    def add_column(self, width: float = None, height: float = None,
                   gutter: float = 0,
                   margins: Sequence[float] = None,
                   render: ContentRenderer = None) -> Column:
        """ Append a new column to the layout. """
        if not width:
            width = self._reference_column_width
        column = Column(width, height, gutter=gutter, margins=margins,
                        render=render)
        self._columns.append(column)
        return column

    def append_paragraphs(self, paragraphs: Iterable[Paragraph]):
        remainer = list(paragraphs)
        # 1. fill existing columns:
        columns = self._columns
        while self._current_column < len(columns):
            column = columns[self._current_column]
            remainer = column.append_paragraphs(remainer)
            if len(remainer) == 0:
                return
            self._current_column += 1

        # 2. create additional columns
        while remainer:
            column = self._new_column()
            self._current_column = len(self._columns) - 1
            remainer = column.append_paragraphs(remainer)
            if self._current_column > 100:
                raise ValueError("Internal error - not enough space!?")

    def _new_column(self) -> Column:
        if len(self._columns) == 0:
            raise ValueError("no column exist")
        empty = self._columns[-1].clone_empty()
        self._columns.append(empty)
        return empty
