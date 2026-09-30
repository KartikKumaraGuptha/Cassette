from PySide6.QtCore import QObject, QPropertyAnimation, QEasingCurve, QAbstractAnimation

class AnimationManager(QObject):
    def animate(self, obj, prop, start, end, duration=350, easing=QEasingCurve.Type.OutCubic):
        property_name = prop.encode() if isinstance(prop, str) else prop
        a = QPropertyAnimation(obj, property_name, self)
        a.setStartValue(start)
        a.setEndValue(end)
        a.setDuration(int(duration))
        a.setEasingCurve(easing)
        a.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        return a
