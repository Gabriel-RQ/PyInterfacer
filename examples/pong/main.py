import pygame

pygame.init()

from pyinterfacer import interfacer as PyInterfacer
from src.setup import setup_interfaces, setup_bindings


class Main:
    def __init__(self) -> None:
        pygame.display.set_caption("Pong")

        self._FULL_SIZE = (
            pygame.display.Info().current_w,
            pygame.display.Info().current_h,
        )
        self._size = self._width, self._height = 800, 600
        self._display = pygame.display.set_mode(self._size, pygame.SCALED, 32)

        self._clock = pygame.time.Clock()
        self._dt = 0
        self._FPS = 120

        self._running = True
        self._fullscreen = False

        setup_interfaces(
            exit_action=self.stop,
            finish_game=self.finish_game,
            full_screen=self.full_screen,
        )

    def finish_game(self):
        PyInterfacer.unload()
        setup_interfaces(
            exit_action=self.stop,
            finish_game=self.finish_game,
            full_screen=self.full_screen,
        )

    def full_screen(self):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self._display = pygame.display.set_mode(
                self._FULL_SIZE, pygame.FULLSCREEN, 32
            )
        else:
            self._display = pygame.display.set_mode(self._size, 0, 32)

        PyInterfacer.unload(backup=True)
        PyInterfacer.reload(raw=True)
        setup_bindings(finish_game=self.finish_game, full_screen=self.full_screen)

    def stop(self):
        self._running = False

    def run(self) -> None:
        paddle_group = PyInterfacer.get_interface("game").get_type_group("paddle")

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.JOYDEVICEADDED:
                    self._controller = pygame.Joystick(event.device_index)
                elif event.type == pygame.JOYDEVICEREMOVED:
                    self._controller = None
                elif event.type == pygame.JOYAXISMOTION:
                    p1 = PyInterfacer.get_component("player1")
                    if event.axis == 1:
                        if event.value < -0.5:
                            p1.move("up")
                        elif event.value > 0.5:
                            p1.move("down")
                        else:
                            p1.stop()
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 7:
                        PyInterfacer.change_focus("game")

                PyInterfacer.handle_event(event)

            PyInterfacer.handle(dt=self._dt)
            paddle_group.handle_victory()

            pygame.display.flip()
            self._dt = self._clock.tick(self._FPS) / 1000


if __name__ == "__main__":
    Main().run()
    pygame.quit()
