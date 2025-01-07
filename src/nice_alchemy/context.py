from dataclasses import dataclass, KW_ONLY, field
import contextvars

# declaring the variable
# to it's default value
field_context = contextvars.ContextVar('current',
                              default = None)

class FieldList():
    def __init__(self):
        self.fields = []

    def __enter__(self):
        self.parent_token = field_context.set(self)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        field_context.reset(self.parent_token)


class FieldContextVisitor():
    def __init__(self):
        # print(field_context.get())
        if field_context.get():
            field_context.get().fields.append(self)
