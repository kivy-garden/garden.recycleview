'''A Label class, which when used with a RecycleView and a
LinearRecycleLayoutManager will display the text in a very efficient manner.

Usage::

    from kivy.garden.recycleview import RecycleView
    from kivy.garden.recycleview.label import LazyLabel
    view = RecycleView(viewclass='LazyLabel', \
scroll_type=['bars', 'content'], bar_width=10)

    view.data = [{
        'text': '\nHello'.join(map(str, range(10000))),
        'halign': 'center', 'color': (0, 1, 1, 1)
    }] * 10000
    runTouchApp(view)
'''

from bisect import bisect_left

from kivy.garden.recycleview import ViewBaseClass, LayoutChangeException
from kivy.uix.label import Label
from kivy.core.text import Label as CoreLabel
from kivy.core.text.markup import MarkupLabel as CoreMarkupLabel
from kivy.utils import get_hex_from_color
from kivy.properties import ListProperty, NumericProperty, BooleanProperty
from kivy.properties import VariableListProperty, ObjectProperty
from kivy.lang import Builder
from kivy.graphics.texture import Texture


Builder.load_string('''
<-LazyLabel>:
    canvas:
        Color:
            rgba: self.disabled_color if self.disabled else \
(self.color if not self.markup else (1, 1, 1, 1))
        Rectangle:
            texture: self.texture
            size: self.true_texture_size
            pos: int(self.center_x - self.texture_size[0] / 2.), \
int(self._texture_pos_y)
''')


def accumulate_lines(lines, y):
    for line in lines:
        yield y
        y += line.h
    yield y


class LazyLabel(Label, ViewBaseClass):
    '''A Label class for use with RecycleView. See module.
    '''

    # y pos of each line within the label widget relative to the top
    _lines_pos = []
    # the y pos of the top of last line
    _last_line_top = 0
    # pos of the smaller rendered texture as tuple of (bottom, top) in
    # coordinates relative to the top of the widget
    _last_rendered_view = None
    _label_cache = {}
    # where we save the default options of the label
    _default_options = None
    # the y pos in the texture (starting from the top) where 1st line starts
    _texture_y = 0
    # the last height of the widget
    _last_height = 0
    # the recycleview used with the label
    _rv = None

    _texture_pos_y = NumericProperty(0)
    '''The pos of the actual texture giving the view into the data.
    '''

    true_texture_size = ListProperty([0, 0])
    '''The size of the texture used for the view. :attr:`texture_size` is the
    size of the overall texture required to hold all the data, even though
    the texture is only the size of :attr:`true_texture_size`.
    '''
    size_to_texture = ListProperty([False, True])
    '''For width, height, whether to set the width, height to the corresponding
    texture width/height of :attr:`texture_size`. Defaults to `[False, True]`
    so that by default, the height will be set to the height of the
    texture.
    '''
    limit_text_width = BooleanProperty(True)
    '''Whether to force :attr:`text_size[0]` to the width of the label.
    Defaults to True.
    '''

    def __init__(self, **kwargs):
        super(LazyLabel, self).__init__(**kwargs)
        def set_text_width(*largs):
            if self.limit_text_width:
                self.text_size[0] = self.width

        def set_size(*largs):
            size_to = self.size_to_texture
            sz = self.texture_size
            if size_to[0]:
                self.width = sz[0]
            if size_to[1]:
                self.height = sz[1]

        self.fbind('width', set_text_width)
        self.fbind('texture_size', set_size)

    def texture_update(self, *largs):
        '''Force texture recreation with the current Label properties.

        After this function call, :attr:`texture_size` will be updated,
        however, no texture will actually be created or rendered and
        :attr:`texture` will remain None. Only when :attr:`refresh_view_layout`
        is called, will the currently visible text be rendered.
        '''
        label = self._label
        mrkup = label.__class__ is CoreMarkupLabel
        self.texture = None
        self._lines_pos = None
        self._last_height = 0
        self.true_texture_size = 0, 0
        if mrkup:
            self.refs = {}
            label._refs = self.refs
            self.anchors = {}
            label._anchors = self.anchors

        if (not label.text or (self.halign[-1] == 'y' or self.strip) and
            not label.text.strip()):
            self.texture_size = (0, 0)
            return

        if mrkup:
            text = self.text
            # we must strip here, otherwise, if the last line is empty,
            # markup will retain the last empty line since it only strips
            # line by line within markup
            if self.halign[-1] == 'y' or self.strip:
                text = text.strip()
            label.text = ''.join((
                '[color=', get_hex_from_color(self.color), ']', text,
                '[/color]'))

        # there are three sizes, internal_size - the actual min size of the
        # text, texture_size - the size of the texture, and label size -
        # the size of this label
        label.resolve_font_name()
        # first pass, calculating width/height
        label._size_texture = sz = label.render()

        # if no text are rendered, return nothing.
        width, height = sz
        if width <= 1 or height <= 1:
            self.texture_size = (0, 0)
            return

        lines = label._cached_lines
        self._default_options = options = label._default_line_options(lines)
        if options is None:  # there was no text to render
            self.texture_size = (0, 0)
            return
        self.texture_size = sz

        ih = label._internal_size[1]  # the real size of text
        valign = options['valign']

        y = ypad = options['padding_y']  # pos within the texture
        if valign == 'bottom':
            y = sz[1] - ih + ypad
        elif valign == 'middle':
            y = int((sz[1] - ih) / 2 + ypad)
        # compute where in the texture the first line should start
        self._texture_y = y

    def _reload_observer(self, *largs):
        self._last_rendered_view = (-1, 0)  # force a redraw
        self._rv.ask_refresh_viewport()

    def refresh_view_attrs(self, rv, data):
        super(LazyLabel, self).refresh_view_attrs(rv, data)
        self._label_cache = {}
        self._rv = rv

    def refresh_view_layout(self, rv, viewport, data, width, height):
        # first set the new size
        super(LazyLabel, self).refresh_view_layout(
            rv, viewport, data, width, height)
        # if we were triggered, do it now
        if self._trigger_texture.is_triggered:
            # This is called at the end of frame already, so don't delay
            self._trigger_texture.cancel()
            self.texture_update()
            # if the size changed we should save it to data
            if self.width != width:
                data['width'] = self.width
                rv.ask_refresh_from_data(extent='data_size')
                # stop execution early so we don't have to draw further
                raise LayoutChangeException()
            if self.height != height:
                data['height'] = self.height
                rv.ask_refresh_from_data(extent='data_size')
                raise LayoutChangeException()

        if self.texture_size == (0, 0):
            return

        view_height = viewport[3] - viewport[1]
        label = self._label
        sz = self.texture_size
        lines = label._cached_lines
        # we need to do the initial setup or if the view became larger
        if (self._lines_pos is None or self._last_height != height or
            self.true_texture_size[1] - 3 * view_height > 0.01):
            tex_height = min(sz[1], 3 * view_height)
            label._size = tex_size = self.true_texture_size = (sz[0], tex_height)

            # The texture will be centered in x dim by kv lang, currently,
            # _texture_y is in coordinates relative to the top of the texture.
            # we need to manually y center the texture in the widget. This
            # transforms it into coordinates relative to the top of the widget
            y = self._texture_y + (self.height - sz[1]) / 2.

            self._lines_pos = list(accumulate_lines(lines, y))
            self._last_line_top = self._lines_pos.pop()
            tex = label.texture = self.texture = Texture.create(
                size=tex_size, mipmap=self._default_options['mipmap'])
            tex.flip_vertical()
            tex.add_reload_observer(self._reload_observer)
            self._last_rendered_view = (-1, 0)
            self._last_height = height

        # now compute the lines to render in the texture
        pos = self._lines_pos
        ylow, yhigh = self._last_rendered_view
        x1, y1, x2, y2 = viewport
        # convert viewport y coords into relative to the top of the widget
        ty1 = self.height - (y1 - self.y)  # bottom of view
        ty2 = self.height - (y2 - self.y)  # top of view
        # the view is within last rendered view
        if ylow - .1 >= ty1 >= ty2 >= yhigh + .1:
            return

        s = bisect_left(pos, ty2 - view_height)
        e = bisect_left(pos, ty1 + view_height, lo=s)
        # for actual rendering include last/first lines not included in case
        # it would show
        s = max(0, s - 1)
        e += 1

        self._texture_pos_y = y1 - view_height
        self._last_rendered_view = ty1 + view_height, ty2 - view_height

        old_opts = label.options
        label._render_begin()
        label.render_lines(
            lines[s:e], self._default_options, label._render_text,
            pos[s] - (ty2 - view_height), self.true_texture_size)
        data = label._render_end()
        label.options = old_opts

        # If the text is 1px width, usually, the data is black.
        # Don't blit that kind of data, otherwise, you have a little black bar.
        if data is not None and data.width > 1:
            label.texture.blit_data(data)
