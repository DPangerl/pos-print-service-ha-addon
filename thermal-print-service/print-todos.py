#!/usr/bin/env python3
"""
Print Todos Service - HA Add-on version
Polls a remote API for todos and prints them on a thermal receipt printer
"""

import os
import time
import requests
import json
import threading
import logging
from datetime import datetime
from print_utils import create_print_job, validate_sections, format_shopping_list, init_printer

# Configuration from environment (set by run.sh from HA options)
BASE_URLS_RAW = os.getenv('BASE_URLS', 'https://todo.dpangerl.de')
BASE_URLS = [url.strip() for url in BASE_URLS_RAW.split(',') if url.strip()]
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))
AUTH_TOKEN = os.getenv('AUTH_TOKEN', '')
PRINTER_DEVICE = os.getenv('PRINTER_DEVICE', '/dev/usb/lp0')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PrintTodosService:
    def __init__(self):
        self.running = False
        self.printer_status = 'unknown'

    def get_auth_headers(self):
        headers = {'Content-Type': 'application/json'}
        if AUTH_TOKEN:
            headers['Authorization'] = f'Bearer {AUTH_TOKEN}'
        return headers

    def print_raw(self, data):
        try:
            with open(PRINTER_DEVICE, 'wb') as printer:
                if isinstance(data, str):
                    printer.write(data.encode('utf-8'))
                else:
                    printer.write(data)
            logger.info('Print successful')
            return True, 'Print successful'
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f'Print failed: {e}')
            return False, f'Print failed: {e}'

    def check_printer_status(self):
        try:
            if not os.path.exists(PRINTER_DEVICE):
                self.printer_status = 'disconnected'
                return 'disconnected'

            # Try direct device access
            try:
                with open(PRINTER_DEVICE, 'wb') as printer:
                    pass
                self.printer_status = 'online'
                return 'online'
            except PermissionError:
                self.printer_status = 'permission_denied'
                return 'permission_denied'
            except Exception:
                self.printer_status = 'device_error'
                return 'device_error'

        except Exception as e:
            logger.error(f'Printer status check failed: {e}')
            self.printer_status = 'error'
            return 'error'

    def fetch_todos(self):
        all_todos = []
        for base_url in BASE_URLS:
            try:
                response = requests.get(f'{base_url}/todos', headers=self.get_auth_headers(), timeout=10)
                if response.status_code == 200:
                    todos = response.json()
                    for todo in todos:
                        todo['_source_url'] = base_url
                    all_todos.extend(todos)
                    if todos:
                        logger.info(f'Fetched {len(todos)} todos from {base_url}')
                else:
                    logger.warning(f'Failed to fetch todos from {base_url}: HTTP {response.status_code}')
            except Exception as e:
                logger.error(f'Error fetching todos from {base_url}: {e}')
        return all_todos

    def delete_todos(self, todos):
        todos_by_url = {}
        for todo in todos:
            source_url = todo.get('_source_url')
            if source_url:
                if source_url not in todos_by_url:
                    todos_by_url[source_url] = []
                todos_by_url[source_url].append(todo.get('id'))

        for base_url, todo_ids in todos_by_url.items():
            if not todo_ids:
                continue
            try:
                response = requests.delete(
                    f'{base_url}/todos',
                    json={'ids': todo_ids},
                    headers=self.get_auth_headers(),
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f'Deleted {len(todo_ids)} todos from {base_url}')
                else:
                    logger.warning(f'Failed to delete todos from {base_url}: HTTP {response.status_code}')
            except Exception as e:
                logger.error(f'Error deleting todos from {base_url}: {e}')

    def send_printer_status(self):
        self.check_printer_status()
        status_data = {
            'current_status': self.printer_status,
            'printer_id': 'thermal-printer',
            'is_online': self.printer_status == 'online',
            'has_error': self.printer_status not in ['online', 'offline'],
            'error_type': self.printer_status if self.printer_status not in ['online', 'offline'] else None,
            'description': self.get_status_description(self.printer_status),
            'can_print': self.printer_status == 'online'
        }

        for base_url in BASE_URLS:
            try:
                response = requests.put(
                    f'{base_url}/printer-status',
                    json=status_data,
                    headers=self.get_auth_headers(),
                    timeout=10
                )
                if response.status_code in [200, 201]:
                    logger.debug(f'Status sent to {base_url}: {self.printer_status}')
                else:
                    logger.warning(f'Failed to send status to {base_url}: HTTP {response.status_code}')
            except Exception as e:
                logger.error(f'Error sending status to {base_url}: {e}')

    def get_status_description(self, status):
        descriptions = {
            'online': 'Printer is ready',
            'offline': 'Printer is not responding',
            'paper_jam': 'Paper jam detected',
            'paper_empty': 'Paper is empty',
            'cover_open': 'Printer cover is open',
            'disconnected': 'Printer not connected via USB',
            'permission_denied': 'No permission to access printer device',
            'device_error': 'Hardware or communication error',
            'error': 'General printer error'
        }
        return descriptions.get(status, 'Unknown status')

    def convert_todos_to_sections(self, todos):
        sections = []
        for todo in todos:
            section = {
                'todo': todo.get('todo', ''),
                'assignee': todo.get('assignee', ''),
                'deadline': todo.get('deadline', todo.get('createdAt', ''))
            }
            sections.append(section)
        return sections

    def process_todos(self):
        status = self.check_printer_status()
        if status != 'online':
            logger.debug(f'Printer not ready ({status}), skipping')
            return

        todos = self.fetch_todos()
        if not todos:
            return

        shopping_lists = [t for t in todos if t.get('type') == 'SHOPPING_LIST']
        regular_todos = [t for t in todos if t.get('type') != 'SHOPPING_LIST']
        printed_todos = []

        for shopping_todo in shopping_lists:
            try:
                title = shopping_todo.get('title', 'Shopping List')
                items = shopping_todo.get('items', [])
                if not items:
                    logger.warning(f'Shopping list "{title}" has no items, skipping')
                    continue

                raw_data = init_printer().encode('utf-8')
                raw_data += format_shopping_list(title, items).encode('utf-8')

                success, message = self.print_raw(raw_data)
                if success:
                    logger.info(f'Printed shopping list: {title} ({len(items)} items)')
                    printed_todos.append(shopping_todo)
                else:
                    logger.error(f'Failed to print shopping list: {message}')
            except Exception as e:
                logger.error(f'Error processing shopping list: {e}')

        if regular_todos:
            sections = self.convert_todos_to_sections(regular_todos)
            try:
                is_valid, error_msg = validate_sections(sections)
                if not is_valid:
                    logger.error(f'Invalid todo sections: {error_msg}')
                else:
                    raw_data = create_print_job(sections)
                    success, message = self.print_raw(raw_data)
                    if success:
                        logger.info(f'Printed {len(regular_todos)} regular todos')
                        printed_todos.extend(regular_todos)
                    else:
                        logger.error(f'Failed to print todos: {message}')
            except Exception as e:
                logger.error(f'Error processing regular todos: {e}')

        if printed_todos:
            todos_with_ids = [t for t in printed_todos if t.get('id')]
            if todos_with_ids:
                self.delete_todos(todos_with_ids)

    def status_sender_loop(self):
        while self.running:
            self.send_printer_status()
            time.sleep(POLL_INTERVAL)

    def main_loop(self):
        while self.running:
            try:
                self.process_todos()
            except Exception as e:
                logger.error(f'Error in main loop: {e}')
            time.sleep(POLL_INTERVAL)

    def start(self):
        logger.info('Starting Thermal Print Service (HA Add-on)')
        logger.info(f'Polling {len(BASE_URLS)} URL(s): {", ".join(BASE_URLS)}')
        logger.info(f'Poll interval: {POLL_INTERVAL}s')
        logger.info(f'Printer device: {PRINTER_DEVICE}')
        logger.info(f'Auth: {"enabled" if AUTH_TOKEN else "disabled"}')

        self.running = True

        status_thread = threading.Thread(target=self.status_sender_loop, daemon=True)
        status_thread.start()

        try:
            self.main_loop()
        except KeyboardInterrupt:
            logger.info('Received interrupt signal')
        finally:
            self.stop()

    def stop(self):
        logger.info('Stopping Thermal Print Service')
        self.running = False


if __name__ == '__main__':
    service = PrintTodosService()
    service.start()
