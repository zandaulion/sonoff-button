import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('listener', Path(__file__).parents[1] / 'src/listener.py')
listener = importlib.util.module_from_spec(spec)
spec.loader.exec_module(listener)


class ButtonSafetyTests(unittest.TestCase):
    def test_each_mouse_button_works_after_release(self):
        for code in range(272, 280):
            with self.subTest(code=code):
                gate = listener.PressGate()
                self.assertTrue(gate.accept(1, code, 1, 1))
                self.assertFalse(gate.accept(1, code, 2, 2))
                self.assertFalse(gate.accept(1, code, 1, 3))
                self.assertFalse(gate.accept(1, code, 0, 3.1))
                self.assertTrue(gate.accept(1, code, 1, 4))

    def test_movement_scrolling_and_typing_never_toggle(self):
        gate = listener.PressGate()
        for event in [(2, 0, 10), (2, 1, 10), (2, 8, 1), (1, 30, 1), (1, 57, 1)]:
            self.assertFalse(gate.accept(*event, 1))

    def test_combined_clicks_and_bounce_do_not_double_toggle(self):
        gate = listener.PressGate()
        self.assertTrue(gate.accept(1, 272, 1, 1))
        self.assertFalse(gate.accept(1, 273, 1, 1.1))
        gate.accept(1, 272, 0, 1.2)
        self.assertFalse(gate.accept(1, 272, 1, 1.3))


if __name__ == '__main__':
    unittest.main()
