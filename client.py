import socket
import threading
import pygame
import time


# message format: type:content,content:end
class Client:
    def __init__(self):
        pygame.init()

        self.running = True
        self.fps = 60

        self.screen_width = 800
        self.screen_height = 600
        self.screen_dimensions = (self.screen_width, self.screen_height)

        self.screen = pygame.display.set_mode(self.screen_dimensions)
        self.clock = pygame.time.Clock()
        self.text_font = pygame.font.Font('data/font.ttf', 15)

        self.hostname = socket.gethostname()
        self.local_ip = socket.gethostbyname(self.hostname)

        pygame.display.set_caption(f'CLIENT: {self.local_ip}')

        self.line_height = self.text_font.get_linesize()
        self.text_max_height = self.screen_height - 35
        self.max_lines = self.text_max_height // self.line_height
        self.last_line_amount = 0
        self.text_offset = 0
        self.user_scrolling = False

        self.screen_text = [
            r'   ________  _____  ______________________',
            r'  / ____/ / / /   |/ ___ / ___ / ____/ __ \ ',
            r' / /   / /_/ / /| | / /   / / / __/ / /_/ /  1. enter the servers IP',
            r'/ /___/ __  / ___ |/ /   / / / /___/ _, _/   2. enter the servers port',
            r'\____/_/ /_/_/  |_/_/   /_/ /_____/_/ |_|',
            ''
                ]
        self.input_message = 'enter host IP>>> '
        self.input_text = ''
        self.input_history = []
        self.history_active = -1

        self.text_type = 'text'
        self.announcement_type = 'announcement'
        self.end_command = 'end'
        self.message_splitter = ':'

        self.text_render = self.render_text()
        self.input_render = self.text_font.render(self.input_message + self.input_text, True, (174, 174, 174))

        # network
        self.is_connected = False
        self.host = None
        self.port = None
        self.buffersize = 4096
        self.address = None

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def run(self):
        while self.running:
            self.clock.tick(self.fps)
            self.screen.fill((12, 12, 12))

            self.handle_input()

            if len(self.screen_text) != self.last_line_amount:
                self.last_line_amount = len(self.screen_text)
                self.text_render = self.render_text()
                if self.text_render.get_height() > self.text_max_height and not self.user_scrolling:
                    self.text_offset = self.text_max_height - self.text_render.get_height()

            self.screen.blit(self.text_render, (0, self.text_offset))

            pygame.draw.rect(self.screen, (12, 12, 12), (5, self.screen_height - self.input_render.get_height() - 20, self.screen_width - 10, self.input_render.get_height() + 20))
            self.screen.blit(self.input_render, (10, self.screen_height - self.input_render.get_height() - 10))
            pygame.draw.rect(self.screen, (174, 174, 174), (5, self.screen_height - self.input_render.get_height() - 15, self.screen_width - 10, self.input_render.get_height() + 10), width=1, border_radius=3)

            pygame.display.update()

        self.send_message(self.build_message(self.text_type, '{quit}'))
        self.client.close()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.key == pygame.K_RETURN:
                    if self.is_connected and self.input_text != '':
                        self.send_message(self.build_message(self.text_type, self.input_text))
                        if self.input_text == '{quit}':
                            self.disconnect_from_server()
                    else:
                        if self.host is None:
                            self.host = self.input_text
                            self.input_message = 'enter host port>>> '
                            self.screen_text.append(f'host ip is set to: {self.host}')
                        elif self.port is None:
                            if self.input_text.isdecimal():
                                self.port = int(self.input_text)
                                self.input_message = '>>> '
                                self.screen_text.append(f'host port is set to: {self.port}')
                                threading.Thread(target=self.connect_to_server).start()
                            else:
                                self.screen_text.append('ERROR: invalid port format!')
                    self.input_history.append(self.input_text)
                    self.input_text = ''
                elif event.key == pygame.K_UP:
                    if len(self.input_history) > 0:
                        if self.history_active == -1:
                            self.history_active = len(self.input_history) - 1
                        else:
                            self.history_active -= 1
                        self.input_text = self.input_history[self.history_active]
                        if self.history_active == -1:
                            self.input_text = ''
                        self.input_render = self.text_font.render(self.input_message + self.input_text, True, (174, 174, 174))
                elif event.key == pygame.K_DOWN:
                    if len(self.input_history) > 0:
                        if self.history_active != -1:
                            self.history_active += 1
                            if self.history_active == len(self.input_history):
                                self.history_active = -1
                            self.input_text = self.input_history[self.history_active]
                            if self.history_active == -1:
                                self.input_text = ''
                            self.input_render = self.text_font.render(self.input_message + self.input_text, True, (174, 174, 174))
                else:
                    self.input_text += event.unicode

                self.input_render = self.text_font.render(self.input_message + self.input_text, True, (174, 174, 174))

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:
                    self.text_offset += 15
                    self.user_scrolling = True
                    if self.text_offset > 0:
                        self.text_offset = 0
                elif event.button == 5:
                    self.text_offset -= 15
                    self.user_scrolling = True
                    if self.text_offset < -self.text_render.get_height() + self.line_height + 10:
                        self.text_offset = -self.text_render.get_height() + self.line_height + 10
                        self.user_scrolling = False

    def connect_to_server(self):
        try:
            self.address = (self.host, self.port)
            self.client.connect(self.address)
            receive_thread = threading.Thread(target=self.get_message)
            receive_thread.start()
            self.is_connected = True
        except OSError:
            self.screen_text.append('ERROR: invalid host information!')
            self.input_message = 'enter host IP>>> '
            self.host = None
            self.port = None
            self.is_connected = False
            self.input_render = self.text_font.render(self.input_message + self.input_text, True, (174, 174, 174))

    def disconnect_from_server(self):
        self.client.close()
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.input_message = 'enter host IP>>> '
        self.host = None
        self.port = None
        self.is_connected = False
        self.input_render = self.text_font.render(self.input_message + self.input_text, True, (174, 174, 174))
        self.screen_text = self.screen_text[:6]

    def get_message(self):
        self.message_splitter = self.client.recv(self.buffersize).decode("utf8")
        while True:
            try:
                raw_message = self.client.recv(self.buffersize).decode("utf8")

                message_list = raw_message.split(self.message_splitter)

                messages = []
                previous_end = 0
                for i, piece in enumerate(message_list):
                    if piece == self.end_command and (i + 1) % 3 == 0:
                        messages.append(message_list[previous_end:i + 1])
                        previous_end = i + 1

                for single_message in messages:
                    if single_message[0] == self.text_type:
                        self.screen_text.append(single_message[1])
                    elif single_message[0] == self.announcement_type:
                        self.screen_text.append(f'HOST {self.host}:{self.port}>>> ' + single_message[1])

            except OSError:  # client disconnected
                break

    def send_message(self, message):
        self.client.send(bytes(message, "utf8"))

    def build_message(self, type, content):
        if type == self.text_type:
            message = f'{type}{self.message_splitter}{content}{self.message_splitter}{self.end_command}{self.message_splitter}'
            return message

    def render_text(self):
        height = len(self.screen_text) * self.line_height + 20
        new_surface = pygame.Surface((self.screen_width, height))
        new_surface.fill((12, 12, 12))
        for i, line in enumerate(self.screen_text):
            new_surface.blit(self.text_font.render(line, True, (174, 174, 174)), (10, 10 + i * self.line_height))

        return new_surface


if __name__ == '__main__':
    Client().run()
