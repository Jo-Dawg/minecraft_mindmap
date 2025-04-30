from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QFileDialog, QVBoxLayout, QMessageBox
)
from PySide6.QtGui import QPainter, QPen, QPixmap, QColor, QMouseEvent, QWheelEvent
from PySide6.QtCore import Qt, QPoint, QRect, QSize
import sys
import os
import json

PROJECT_VERSION = 1


class Node:
    def __init__(self, image_path, position):
        self.image_path = image_path
        self.image = QPixmap(image_path)
        self.position = position
        self.size = self.image.size()
        self.rect = self.image.rect().translated(position)

    def contains(self, point):
        return self.rect.contains(point)

    def center_right(self):
        return self.position + QPoint(self.size.width(), self.size.height() // 2)

    def center_left(self):
        return self.position + QPoint(0, self.size.height() // 2)

    def move_to(self, point):
        self.position = point
        self.rect.moveTo(point)


class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1200, 900)
        self.nodes = []
        self.connections = []
        self.dragging_node = None
        self.offset = QPoint()
        self.creating_link = False
        self.deleting_link = False
        self.link_start_node = None
        self.virtual_start_point = None
        self.background_image = None
        self.snap_lines = []

        self.scale = 1.0
        self.translation = QPoint(0, 0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.translation)
        painter.scale(self.scale, self.scale)

        if self.background_image:
            painter.drawPixmap(self.rect(), self.background_image)

        pen = QPen(QColor(150, 150, 150), 2 / self.scale)
        painter.setPen(pen)

        for n1, n2 in self.connections:
            p1 = n1.center_right()
            p2 = n2.center_left()
            mid_x = (p1.x() + p2.x()) // 2
            path = [p1, QPoint(mid_x, p1.y()), QPoint(mid_x, p2.y()), p2]
            for i in range(len(path) - 1):
                painter.drawLine(path[i], path[i + 1])

        # Nodes
        for node in self.nodes:
            painter.drawPixmap(node.position, node.image)

        # Snap-Lines
        guide_pen = QPen(Qt.green, 1, Qt.DashLine)
        painter.setPen(guide_pen)
        for line in self.snap_lines:
            painter.drawLine(*line)

        # Auswahl hervorheben
        if self.creating_link and self.link_start_node:
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.link_start_node.rect)
        elif self.creating_link and self.virtual_start_point:
            pen = QPen(Qt.darkYellow, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawEllipse(self.virtual_start_point, 6, 6)

    def transform_pos(self, pos):
        return (pos - self.translation) / self.scale
    
    def mousePressEvent(self, event: QMouseEvent):
        if self.deleting_link:
            clicked_line = self.find_connection_at(event.pos())
            if clicked_line:
                self.connections.remove(clicked_line)
                self.update()
                return

        # Verbindung als Startpunkt
        if self.creating_link:
            virtual_point = self.find_virtual_connection_point(event.pos())
            if virtual_point:
                self.virtual_start_point = virtual_point
                self.link_start_node = None
                self.update()
                return

        clicked_node = None
        for node in reversed(self.nodes):
            if node.contains(event.pos()):
                clicked_node = node
                break

        if self.creating_link:
            if (self.link_start_node or self.virtual_start_point) and clicked_node:
                self.connections.append((self.link_start_node or self.virtual_start_point, clicked_node))
                self.creating_link = False
                self.link_start_node = None
                self.virtual_start_point = None
                self.update()
                return
            elif clicked_node:
                self.link_start_node = clicked_node
                self.virtual_start_point = None
                self.update()
                return

        if clicked_node:
            self.dragging_node = clicked_node
            self.offset = event.pos() - clicked_node.position

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging_node:
            new_pos = event.pos() - self.offset
            self.snap_lines.clear()

            snap_threshold = 10
            this_center = new_pos + QPoint(self.dragging_node.size.width() // 2, self.dragging_node.size.height() // 2)

            for other in self.nodes:
                if other is self.dragging_node:
                    continue
                other_center = other.position + QPoint(other.size.width() // 2, other.size.height() // 2)
                if abs(this_center.x() - other_center.x()) < snap_threshold:
                    this_center.setX(other_center.x())
                    new_pos.setX(other.position.x())
                    self.snap_lines.append((QPoint(this_center.x(), 0), QPoint(this_center.x(), self.height())))
                if abs(this_center.y() - other_center.y()) < snap_threshold:
                    this_center.setY(other_center.y())
                    new_pos.setY(other.position.y())
                    self.snap_lines.append((QPoint(0, this_center.y()), QPoint(self.width(), this_center.y())))

            self.dragging_node.move_to(new_pos)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging_node = None
        self.snap_lines.clear()
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.2 if angle > 0 else 1 / 1.2
            old_pos = self.transform_pos(event.position().toPoint())
            self.scale *= factor
            new_pos = self.transform_pos(event.position().toPoint())
            self.translation += (new_pos - old_pos) * self.scale
            self.update()
        else:
            delta = event.angleDelta()
            self.translation += QPoint(delta.x(), delta.y()) * 0.5
            self.update()

    def add_node_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Bild auswählen", "", "Bilder (*.png *.jpg *.jpeg)"
        )
        if file_path:
            new_node = Node(file_path, QPoint(400, 300))
            self.nodes.append(new_node)
            self.update()

    def enable_link_creation(self):
        self.creating_link = True
        self.deleting_link = False
        self.link_start_node = None
        self.virtual_start_point = None
        self.update()

    def enable_link_deletion(self):
        self.creating_link = False
        self.deleting_link = True
        self.link_start_node = None
        self.virtual_start_point = None
        self.update()

    def load_background_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Hintergrundbild laden", "", "Bilder (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.background_image = QPixmap(file_path)
            self.update()

    def find_connection_at(self, pos):
        tolerance = 6
        for conn in self.connections:
            p1 = self.resolve_point(conn[0], "right")
            p2 = self.resolve_point(conn[1], "left")
            mid_x = (p1.x() + p2.x()) // 2
            path = [p1, QPoint(mid_x, p1.y()), QPoint(mid_x, p2.y()), p2]
            for i in range(len(path) - 1):
                segment = QRect(path[i], path[i + 1]).normalized().adjusted(-tolerance, -tolerance, tolerance, tolerance)
                if segment.contains(pos):
                    return conn
        return None

    def find_virtual_connection_point(self, pos):
        tolerance = 8
        for conn in self.connections:
            p1 = self.resolve_point(conn[0], "right")
            p2 = self.resolve_point(conn[1], "left")
            mid_x = (p1.x() + p2.x()) // 2
            mid_y = (p1.y() + p2.y()) // 2
            mid_point = QPoint(mid_x, mid_y)
            if QRect(mid_point - QPoint(tolerance, tolerance), QSize(tolerance * 2, tolerance * 2)).contains(pos):
                return QPoint(mid_x, mid_y)
        return None

    def resolve_point(self, obj, side):
        if isinstance(obj, Node):
            return obj.center_right() if side == "right" else obj.center_left()
        elif isinstance(obj, QPoint):
            return obj
        return QPoint(0, 0)

    def save_to_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Projekt speichern", "", "Projektdateien (*.json)"
        )
        if file_path:
            data = {
                "version": PROJECT_VERSION,
                "nodes": [
                    {"image_path": node.image_path, "x": node.position.x(), "y": node.position.y()}
                    for node in self.nodes
                ],
                "connections": [
                    {"from": self.nodes.index(c[0]) if isinstance(c[0], Node) else {"virtual": [c[0].x(), c[0].y()]},
                     "to": self.nodes.index(c[1])}
                    for c in self.connections
                ]
            }
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)

    def load_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Projekt laden", "", "Projektdateien (*.json)"
        )
        if file_path and os.path.exists(file_path):
            with open(file_path, "r") as f:
                try:
                    data = json.load(f)
                    if "version" not in data or data["version"] != PROJECT_VERSION:
                        QMessageBox.warning(self, "Versionswarnung", "Dieses Projekt stammt aus einer anderen Version.")
                    self.nodes = []
                    for entry in data["nodes"]:
                        if os.path.exists(entry["image_path"]):
                            node = Node(entry["image_path"], QPoint(entry["x"], entry["y"]))
                            self.nodes.append(node)
                        else:
                            QMessageBox.warning(self, "Fehlendes Bild", f"{entry['image_path']} wurde nicht gefunden.")
                    self.connections = []
                    for conn in data.get("connections", []):
                        start = conn["from"]
                        if isinstance(start, dict) and "virtual" in start:
                            start_point = QPoint(start["virtual"][0], start["virtual"][1])
                        else:
                            start_point = self.nodes[start]
                        end = self.nodes[conn["to"]]
                        self.connections.append((start_point, end))
                    self.update()
                except Exception as e:
                    QMessageBox.critical(self, "Fehler beim Laden", str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft Mindmap")

        self.canvas = Canvas()
        self.button_add = QPushButton("Bild hinzufügen")
        self.button_link = QPushButton("Verbindung erstellen")
        self.button_delete = QPushButton("Verbindung löschen")
        self.button_background = QPushButton("Hintergrund laden")
        self.button_save = QPushButton("Speichern")
        self.button_load = QPushButton("Laden")

        self.button_add.clicked.connect(self.canvas.add_node_from_file)
        self.button_link.clicked.connect(self.canvas.enable_link_creation)
        self.button_delete.clicked.connect(self.canvas.enable_link_deletion)
        self.button_background.clicked.connect(self.canvas.load_background_image)
        self.button_save.clicked.connect(self.canvas.save_to_file)
        self.button_load.clicked.connect(self.canvas.load_from_file)

        layout = QVBoxLayout()
        layout.addWidget(self.button_add)
        layout.addWidget(self.button_link)
        layout.addWidget(self.button_delete)
        layout.addWidget(self.button_background)
        layout.addWidget(self.button_save)
        layout.addWidget(self.button_load)
        layout.addWidget(self.canvas)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())