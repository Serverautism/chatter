import socket
import threading
import pygame
import time
import random
import datetime
import json


# message format: type:content,content:end
class Server:
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

        self.line_height = self.text_font.get_linesize()
        self.text_max_height = self.screen_height - 35
        self.max_lines = self.text_max_height // self.line_height
        self.text_offset = 0
        self.last_line_amount = 0
        self.user_scrolling = False

        self.hostname = socket.gethostname()
        self.local_ip = socket.gethostbyname(self.hostname)

        pygame.display.set_caption(f'SERVER: {self.local_ip}')

        self.text_type = 'text'
        self.announcement_type = 'announcement'
        self.end_command = 'end'
        self.message_splitter = ''.join(chr(random.randint(33, 126)) for _ in range(10))

        self.screen_text = []
        self.input_message = '>>> '
        self.input_text = ''
        self.input_history = []
        self.history_active = -1

        self.text_render = self.render_text()
        self.input_render = self.text_font.render(self.input_message + self.input_text, True, (174, 174, 174))
        
        self.session_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.shutdown_timer = -2
        self.shutdown_timer_count = 0

        self.error_event = 'ERROR: '
        self.usage_error_event = 'USAGE ERROR: '
        self.user_info_event = 'USER INFO: '
        self.commands = [['!broadcast', '!broadcast <message>'], ['!getinfo', '!getinfo <username>'], ['!setop', '!setop <username>'], ['!help', '!help <optional: command>'], ['!stop', '!stop <optional: seconds>']]

        # network
        self.addresses = {}
        self.clients = {}
        with open('data/saves/admins.json', 'r') as f:
            self.admins = json.load(f)

        self.host = ''
        self.port = 25565
        self.buffersize = 4096
        self.address = (self.host, self.port)

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(self.address)

    def run(self):
        self.server.listen(5)
        self.log('Waiting for connection...')
        accept_thread = threading.Thread(target=self.accept_new_connections)
        accept_thread.start()

        while self.running:
            self.clock.tick(self.fps)
            self.screen.fill((12, 12, 12))

            self.handle_input()

            if self.shutdown_timer > 0:
                self.shutdown_timer_count += 1
                if self.shutdown_timer_count == self.fps:
                    self.shutdown_timer_count = 0
                    self.shutdown_timer -= 1
                    if self.shutdown_timer == 0:
                        self.running = False

            if len(self.screen_text) != self.last_line_amount:
                self.text_render = self.render_text()
                self.last_line_amount = len(self.screen_text)
                if self.text_render.get_height() > self.text_max_height and not self.user_scrolling:
                    self.text_offset = self.text_max_height - self.text_render.get_height()

            self.screen.blit(self.text_render, (0, self.text_offset))

            pygame.draw.rect(self.screen, (12, 12, 12), (5, self.screen_height - self.input_render.get_height() - 20, self.screen_width - 10, self.input_render.get_height() + 15))
            self.screen.blit(self.input_render, (10, self.screen_height - self.input_render.get_height() - 10))
            pygame.draw.rect(self.screen, (174, 174, 174), (5, self.screen_height - self.input_render.get_height() - 15, self.screen_width - 10, self.input_render.get_height() + 10), width=1, border_radius=3)

            pygame.display.update()

        self.broadcast(self.build_message(self.announcement_type, 'Server stopped'))

        for sock in self.clients:
            sock.close()
        self.server.close()

        with open('data/saves/admins.json', 'w') as f:
            json.dump(self.admins, f, indent=4)

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.key == pygame.K_RETURN:
                    if self.input_text != '':
                        self.handle_command(self.input_text)
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

            elif event.type == pygame.MOUSEBUTTONDOWN:
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

    def accept_new_connections(self):
        while True:
            try:
                client, client_address = self.server.accept()
                self.log(f'{client_address[0]}:{client_address[1]} has connected, requesting name')
                self.addresses[client] = client_address
                threading.Thread(target=self.handle_client, args=(client,)).start()
            except OSError:
                break

    def handle_client(self, client):
        client.send(bytes(self.message_splitter, 'utf8'))
        time.sleep(1)
        client.send(bytes(self.build_message(self.announcement_type, 'please submit your name before joining the chat.'), 'utf8'))

        name = client.recv(self.buffersize).decode('utf8').split(self.message_splitter)[1]
        client.send(bytes(self.build_message(self.announcement_type, f'Welcome {name}! Send {{quit}} to exit.'), 'utf8'))

        if self.addresses[client][0] in self.admins:
            client.send(bytes(self.build_message(self.announcement_type, 'you are an admin'), 'utf8'))

        self.broadcast(self.build_message(self.announcement_type, f'{name}  joined!'))
        self.clients[client] = name

        client_ip = self.addresses[client][0]
        client_address = self.addresses[client][1]

        self.log(f'{client_ip}:{client_address} registered name {name}')

        client_active = True

        while client_active:
            raw_message = client.recv(self.buffersize).decode('utf8')

            message_list = raw_message.split(self.message_splitter)

            messages = []
            previous_end = 0
            for i, piece in enumerate(message_list):
                if piece == self.end_command and (i + 1) % 3 == 0:
                    messages.append(message_list[previous_end:i + 1])
                    previous_end = i + 1

            for single_message in messages:
                if single_message[0] == self.text_type:
                    if single_message[1] != '{quit}':
                        if single_message[1].split()[0] in [command[0] for command in self.commands]:
                            if client_ip in self.admins and self.admins[client_ip] == 1:
                                self.handle_command(single_message[1], client)
                            else:
                                client.send(bytes(self.build_message(self.announcement_type, 'You are not allowed to use commands in this chat!'), 'utf8'))
                        else:
                            self.broadcast(self.build_message(self.text_type, f'{name}: ' + single_message[1]))
                    else:
                        client.close()
                        del self.clients[client]
                        self.log(f'{name} disconnected.')
                        self.broadcast(self.build_message(self.announcement_type, f'{name} left.'))
                        client_active = False

    def broadcast(self, message):
        for sock in self.clients:
            sock.send(bytes(message, 'utf8'))

    def build_message(self, type, content):
        if type == self.text_type or type == self.announcement_type:
            message = f'{type}{self.message_splitter}{content}{self.message_splitter}{self.end_command}{self.message_splitter}'
            return message

    def log(self, text, event=''):
        if isinstance(text, str):
            logging_text = f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {event}{text}'
            self.screen_text.append(logging_text)
        elif isinstance(text, list):
            for i, line in enumerate(text):
                if i == 0:
                    logging_text = f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {event}{line}'
                    self.screen_text.append(logging_text)
                else:
                    date_spaces = ''.join(' ' for _ in datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    event_spaces = ''.join(' ' for _ in event)
                    logging_text = f' {date_spaces}  {event_spaces}{line}'
                    self.screen_text.append(logging_text)

    def handle_command(self, raw_command, client=None):
        command = raw_command.split()

        # broadcast
        if command[0] == self.commands[0][0]:
            if len(command) > 1:
                message = ''.join(c + ' ' for c in command[1:])
                message = self.build_message(self.announcement_type, message)
                self.broadcast(message)
                if client is None:
                    self.log(raw_command)
                else:
                    self.log(f'{self.clients[client]} used: {raw_command}')
            else:
                if client is None:
                    self.log(self.commands[0][1], self.usage_error_event)
                else:
                    client.send(bytes(self.build_message(self.announcement_type, self.usage_error_event + self.commands[0][1]), 'utf8'))

        # get info
        elif command[0] == self.commands[1][0]:
            if len(command) == 2:
                found = False
                for c in self.clients.items():
                    if c[1] == command[1]:
                        is_admin = False
                        if self.addresses[c[0]][0] in self.admins:
                            is_admin = True
                        text = f'address: {self.addresses[c[0]]}, is admin: {is_admin}'
                        if client is None:
                            self.log(text, self.user_info_event)
                        else:
                            self.log(f'{self.clients[client]} used: {raw_command}')
                            client.send(bytes(self.build_message(self.announcement_type, text), 'utf8'))
                        found = True
                if not found:
                    if client is None:
                        self.log('no user with this name found', self.error_event)
                    else:
                        client.send(bytes(self.build_message(self.announcement_type, self.error_event + 'no user with this name found'), 'utf8'))
            else:
                if client is None:
                    self.log(self.commands[1][1], self.usage_error_event)
                else:
                    client.send(bytes(self.build_message(self.announcement_type, self.error_event + self.commands[1][1]), 'utf8'))

        # set op
        elif command[0] == self.commands[2][0]:
            if len(command) == 2:
                found = False
                for c in self.clients.items():
                    if c[1] == command[1]:
                        ip = self.addresses[c[0]][0]
                        if ip in self.admins:
                            if self.admins[ip] == 1:
                                if client is None:
                                    self.log(f'{command[1]} is already an admin')
                                else:
                                    self.log(f'{self.clients[client]} used: {raw_command}')
                                    client.send(bytes(self.build_message(self.announcement_type, f'{command[1]} is already an admin'), 'utf8'))
                            else:
                                self.admins[ip] = 1
                                c[0].send(bytes(self.build_message(self.announcement_type, 'you are now an admin'), 'utf8'))
                                if client is None:
                                    self.log(f'added {command[1]} back to the admins')
                                else:
                                    self.log(f'{self.clients[client]} used: {raw_command}')
                                    client.send(bytes(self.build_message(self.announcement_type, f'added {command[1]} back to the admins'), 'utf8'))
                        else:
                            self.admins[ip] = 1
                            c[0].send(bytes(self.build_message(self.announcement_type, 'you are now an admin'), 'utf8'))
                            if client is None:
                                self.log(f'added {command[1]} to the admins')
                            else:
                                self.log(f'{self.clients[client]} used: {raw_command}')
                                client.send(bytes(self.build_message(self.announcement_type, f'added {command[1]} to the admins'), 'utf8'))
                        found = True
                if not found:
                    if client is None:
                        self.log('no user with this name found', self.error_event)
                    else:
                        client.send(bytes(self.build_message(self.announcement_type, self.error_event + 'no user with this name found'), 'utf8'))
            else:
                if client is None:
                    self.log(self.commands[2][1], self.usage_error_event)
                else:
                    client.send(bytes(self.build_message(self.announcement_type, self.error_event + self.commands[2][1]), 'utf8'))

        # help
        elif command[0] == self.commands[3][0]:
            if len(command) == 1:
                if client is None:
                    to_log = []
                    for c in self.commands:
                        to_log.append(f'command: {c[0]}, usage: {c[1]}')
                    self.log(to_log)
                else:
                    for c in self.commands:
                        client.send(bytes(self.build_message(self.announcement_type, f'command: {c[0]}, usage: {c[1]}'), 'utf8'))
                    self.log(f'{self.clients[client]} used: {raw_command}')
            elif len(command) == 2:
                found = False
                for c in self.commands:
                    if command[1] == c[0]:
                        if client is None:
                            self.log(f'command: {c[0]}, usage: {c[1]}')
                        else:
                            client.send(bytes(self.build_message(self.announcement_type, f'command: {c[0]}, usage: {c[1]}'), 'utf8'))
                            self.log(f'{self.clients[client]} used: {raw_command}')
                        found = True

                if not found:
                    if client is None:
                        self.log('no command with this name found', self.error_event)
                    else:
                        client.send(bytes(self.build_message(self.announcement_type, self.error_event + 'no command with this name found'), 'utf8'))
            else:
                if client is None:
                    self.log(self.commands[3][1], self.usage_error_event)
                else:
                    client.send(bytes(self.build_message(self.announcement_type, self.error_event + self.commands[3][1]), 'utf8'))

        # stop
        elif command[0] == self.commands[4][0]:
            if len(command) == 1:
                self.running = False
                self.log('Server stopped')
            elif len(command) == 2:
                if command[1].isdecimal():
                    self.shutdown_timer = int(command[1])
                    self.log(f'Server will shutdown in {self.shutdown_timer} seconds')
                    self.broadcast(self.build_message(self.announcement_type, f'Server will shutdown in {self.shutdown_timer} seconds'))
                else:
                    if client is None:
                        self.log(self.commands[4][1], self.usage_error_event)
                    else:
                        client.send(bytes(self.build_message(self.announcement_type, self.error_event + self.commands[4][1]), 'utf8'))
            else:
                self.log(self.commands[1][1], self.usage_error_event)

        # bad command
        else:
            self.log('this is not a supported command!', event=self.error_event)

    def render_text(self):
        height = len(self.screen_text) * self.line_height + 20
        new_surface = pygame.Surface((self.screen_width, height))
        new_surface.fill((12, 12, 12))
        for i, line in enumerate(self.screen_text):
            new_surface.blit(self.text_font.render(line, True, (174, 174, 174)), (10, 10 + i * self.line_height))

        return new_surface


if __name__ == '__main__':
    Server().run()
