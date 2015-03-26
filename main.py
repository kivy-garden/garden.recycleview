from recycleview import RecycleView
from kivy.base import runTouchApp
from kivy.lang import Builder
from kivy.app import App
from kivy.metrics import sp
import random

Builder.load_string("""
<ContactSeparator@Widget>:
    canvas.before:
        Color:
            rgb: (.5, .5, .5)
        Rectangle:
            pos: self.pos
            size: self.size

<ContactItem@BoxLayout>:
    index: 0
    contact_media: ""
    contact_name: ""
    spacing: "10dp"

    canvas.before:
        Color:
            rgb: (1, 1, 1) if root.index % 2 == 0 else (.95, .95, .95)
        Rectangle:
            pos: self.pos
            size: self.size

    AsyncImage:
        source: root.contact_media
        size_hint_x: None
        width: self.height
        allow_stretch: True
    Label:
        font_size: "20sp"
        text: root.contact_name
        color: (0, 0, 0, 1)
        text_size: (self.width, None)
""")

class RecycleViewApp(App):
    def build(self):
        # Create a data set
        contacts = []
        names = ["Robert", "George", "Joseph", "Donald", "Mark", "Anthony", "Gary"]
        medias = [
            "http://pbs.twimg.com/profile_images/3312895495/8e39061bdad2b5d18dc8a9be63a2f50a_normal.png",
            "http://www.geglobalresearch.com/media/Alhart-Todd-45x45.jpg",
        ]
        for x in range(1000):
            if x % 20 == 0:
                contacts.append({
                    "viewclass": "ContactSeparator",
                    "height": sp(20)
                })
            contacts.append({
                "index": x,
                "viewclass": "ContactItem",
                "contact_media": random.choice(medias),
                "contact_name": "{} {}".format(
                    random.choice(names),
                    random.choice(names)
                )
            })

        rv = RecycleView()
        rv.key_viewclass = "viewclass"
        rv.key_height = "height"
        rv.data = contacts
        return rv

RecycleViewApp().run()
