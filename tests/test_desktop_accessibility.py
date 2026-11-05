"""Native Qt accessibility tree and actual focus rendering (not reader proof)."""
import tempfile
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QAccessible, QImage, QPainter
from PySide6.QtWidgets import QStyleOptionViewItem, QStyle
from PySide6.QtTest import QTest
from test_desktop_redesign import make_window


def test_native_accessible_items_and_live_update():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            accessible=QAccessible.queryAccessibleInterface(w.cue_list)
            names=[accessible.child(i).text(QAccessible.Name) for i in range(accessible.childCount())]
            assert any('Description 2, 00:20.0 to 00:24.0, Needs review' in s and 'Identity uncertain' in s for s in names)
            QTest.keyClicks(w.text,'New')
            assert 'New' in w.cue_list.item(0).data(Qt.AccessibleTextRole)
            assert 'New' in w.timeline.blocks[0].accessibleName()
            w.undo_stack.undo();assert 'New' not in w.cue_list.item(0).data(Qt.AccessibleTextRole)
        finally:w.dirty=False;w.close();app.processEvents()


def test_focus_paints_distinct_cue_border_and_contrast():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            def render(focus):
                image=QImage(300,108,QImage.Format_ARGB32);image.fill(Qt.white)
                painter=QPainter(image);option=QStyleOptionViewItem();option.rect=QRect(0,0,300,108);option.palette=w.palette()
                option.state=QStyle.State_Enabled|(QStyle.State_HasFocus if focus else QStyle.State_None)
                w.cue_list.itemDelegate().paint(painter,option,w.cue_list.model().index(0,0));painter.end()
                return image
            assert render(False)!=render(True)
            def luminance(color):
                channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
                return sum(a*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for a,v in zip((.2126,.7152,.0722),channels))
            assert (luminance('#ffffff')+.05)/(luminance('#416180')+.05)>=4.5
            for theme in ('light','dark'):
                w.settings.data['ui_theme']=theme;w.apply_theme()
                assert 'background:#416180;color:#ffffff' in w.styleSheet()
                assert 'QPushButton[role="primary"]:focus' in w.styleSheet()
        finally:w.dirty=False;w.close();app.processEvents()
