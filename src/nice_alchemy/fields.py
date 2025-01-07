from typing import Any, Callable, DefaultDict, Dict, Iterable, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, KW_ONLY, field
from pprint import pprint
import operator

from nicegui import ui
import nicegui.binding as binding
from sqlalchemy_utils import get_class_by_table
from sqlalchemy import select, inspect, bindparam
from sqlalchemy.orm.attributes import InstrumentedAttribute
import sqlalchemy

import nice_alchemy.context as context
import nice_alchemy

model_base = None
sessionmaker = None


def __set__(self, instance: Any, value: Any) -> None:
    value_same = self.__get__(instance, None) == value
    if value_same:
        return
    self.__set(instance, value)

    binding._propagate(instance, self.key)
    if not value_same and self._change_handler:
        self._change_handler[0](instance, value)


def set_handler(self, handler):
    if not self._change_handler and handler:
        self._change_handler.append(handler)


InstrumentedAttribute.__set = InstrumentedAttribute.__set__
InstrumentedAttribute.__set__ = __set__
InstrumentedAttribute._change_handler = []
InstrumentedAttribute.set_handler = set_handler


def make_bindable(instance, attr, attr_type=None, on_change: Optional[Callable[..., Any]] = None):
    binder = getattr(instance.__class__, attr)
    binder.set_handler(on_change)
    temp = getattr(instance, attr)

    binding.bindable_properties[(id(instance), attr)] = instance
    setattr(instance, attr, temp)


def set_model_base(base):
    global model_base
    model_base = base


def set_sessionmaker(db):
    global sessionmaker
    sessionmaker = db


def get_sessionmaker():
    global sessionmaker
    return sessionmaker


def get_model_from_row(row):
    return row.__class__._sa_class_manager.class_


def get_pk_names(row):
    return [get_prop_by_column(pk_column) for pk_column in row.__class__.__table__.primary_key.columns.values()]


def get_prop_by_column(column, model=None):
    if not model:
        model = get_class_by_column(column)
    for key, col in vars(model).items():
        if col == column:
            return key


def fk_class(column):
    global model_base
    if column.foreign_keys:
        for key in column.foreign_keys:
            return get_class_by_table(model_base, key.column.table)
    return None


def get_class_by_column(column):
    return get_class_by_table(model_base, column.table)


def get_backref(model, target):
    global model_base
    for key, item in inspect(model).attrs.items():
        if hasattr(item, 'backref') and get_class_by_table(model_base, item.target) == target:
            return key
    return None


class ChipToggle(ui.chip):
    def __init__(self, *args, **kwargs):
        if 'alt_icon' in kwargs:
            self.icons = [kwargs['icon'], kwargs['alt_icon']]
            kwargs.pop('alt_icon', None)
        else:
            self.icons = None

        self.alt_icon = False

        super().__init__(*args, **kwargs)

    def set_icon(self, icon: str):
        self._props['icon'] = icon
        self.update()

    def toggle(self):
        if self.icons:
            self.alt_icon = not (self.alt_icon)
            self.set_icon(self.icons[int(self.alt_icon)])
        return self.alt_icon


@dataclass
class Field(context.FieldContextVisitor):
    bind_values = {}
    _: KW_ONLY
    event_handlers: list = None
    backward: callable = None
    forward: callable = None
    autofill = True

    def __post_init__(self):
        context.FieldContextVisitor.__init__(self)

    def set_source_field_value(self, value):
        Field.bind_values[self.col_prop] = value

    def get_source_field_value(self, id):
        if id in Field.bind_values.keys():
            return Field.bind_values[id]
        else:
            return None

    def create_bindparam(self):
        param = bindparam(key='id', callable_=lambda id=self.col_prop: self.get_source_field_value(id))
        return param

    def create_bindable_callbacks(self, element_row, data_row):
        bind_funcs = {}
        if self.backward:
            backward = self.backward
            bind_funcs['backward'] = lambda value, r=data_row: self.backward(value, r)
        if self.forward:
            forward = self.forward
            bind_funcs['forward'] = lambda value, r=data_row: forward(value, r)
        return bind_funcs

    def add_handlers(self, element, event_handlers):
        if isinstance(event_handlers, tuple):
            element.on(*event_handlers)
        elif isinstance(event_handlers, list):
            for event in event_handlers:
                element.on(*event)


@dataclass
class Relation(Field):
    def __post_init__(self):
        Field.__post_init__(self)
        self.model = fk_class(self.col)
        self.col_prop = get_prop_by_column(self.col)

    label: str
    col: object


@dataclass
class Value(Relation):

    _: KW_ONLY
    type: object = ui.input

    def __post_init__(self):
        Relation.__post_init__(self)
        self.model = get_class_by_column(self.col)
        self.col_prop = get_prop_by_column(self.col, self.model)

    def create_element(self, element_row, data_row, event_handlers=None):
        element = self.type(self.label)
        if self.autofill:
            element.props('autocomplete="new-password"')
        element.element_row = element_row
        element.data_row = data_row

        make_bindable(data_row, self.col_prop, attr_type=type(element.value))

        element.bind_value(data_row, self.col_prop, **self.create_bindable_callbacks(element_row, data_row))

        self.add_handlers(element, event_handlers)
        self.add_handlers(element, self.event_handlers)

        element_row[self.col_prop] = element
        return element


def update_list_options(target_field, element, session, value=None):
    if hasattr(target_field, 'source'):
        target_field.source.set_source_field_value(value)

    if target_field.stmt is not None:
        stmt = select(target_field.model).from_statement(target_field.stmt)
    else:
        stmt = select(target_field.model)
    with session.no_autoflush:
        option_items = session.scalars(stmt).all()
    options = {}
    option_data = {}
    for item in option_items:
        label = operator.attrgetter(target_field.relation_chain.split('.', 1)[1])(item)
        options[getattr(item, get_pk_names(item)[0])] = label
        option_data[getattr(item, get_pk_names(item)[0])] = item
    element.set_options(options)
    element.option_data = option_data
    return options, option_data


@dataclass
class FilterableField(Relation):

    _: KW_ONLY
    options: list = None
    option_data: dict = None

    def __post_init__(self):
        Relation.__post_init__(self)

    def bind_source(self, source):
        param = source.create_bindparam()
        self.source = source
        source.target = self
        return param

    def set_filterable_options(self, element, element_row, session):
        if hasattr(self, 'source'):
            if self.source.col_prop in element_row and element_row[self.source.col_prop] is not None:
                update_list_options(self, element, session, element_row[self.source.col_prop].value)
            else:
                print(
                    f'Warning! {self.source.col_prop} element doesnt exist yet.  Make sure to update list options at end of ro creation'
                )

            func = lambda e, f=self, el=element, s=session: update_list_options(f, el, s, e.value)
            element_row[self.source.col_prop].on_value_change(func)

        elif self.options:
            element.set_options(self.options)
            element.option_data = self.option_data
        else:
            self.options, self.option_data = update_list_options(self, element, session)


@dataclass
class RelationPaired(Relation, context.FieldList):  # 1:1 relationship
    def __post_init__(self):
        Relation.__post_init__(self)
        context.FieldList.__init__(self)

    def get_backref(self, model):
        # print(model, self.model)
        self.rel_attr = get_backref(model, self.model)

    def create_element(self, element_row, data_row, backref=None):
        if backref:
            self.get_backref(backref)
        # print(self.rel_attr)
        if getattr(data_row, self.rel_attr) is None:
            att_item = self.model()
            setattr(data_row, self.rel_attr, att_item)
        if self.event_handlers:
            self.add_handlers(element, self.event_handlers)


@dataclass
class RelationSingle(FilterableField):  # m:1 relationship

    _: KW_ONLY
    relation_chain: str = ''

    def __post_init__(self):
        FilterableField.__post_init__(self)
        self.stmt = select(self.model)

    def get_backref(self, model):
        self.rel_attr = get_backref(model, self.model)

    def create_element(self, element_row, data_row, session, backref=None, event_handlers=None):
        if backref:
            self.get_backref(backref)
        element = ui.select(label=self.label, with_input=True, options={})
        element.element_row = element_row
        element.data_row = data_row

        make_bindable(data_row, self.col_prop, attr_type=type(element.value))

        def change(event):
            if event.value:
                setattr(data_row, self.rel_attr, element.option_data[event.value])

        element.on_value_change(change)
        if self.autofill:
            element.props('autocomplete="new-password"')

        self.set_filterable_options(element, element_row, session)
        self.add_handlers(element, event_handlers)
        self.add_handlers(element, self.event_handlers)

        element.bind_value(data_row, self.col_prop, **self.create_bindable_callbacks(element_row, data_row))
        element_row[self.col_prop] = element
        return element


@dataclass
class RelationList(FilterableField, context.FieldList):  # m:m relationship
    def __post_init__(self):
        FilterableField.__post_init__(self)
        context.FieldList.__init__(self)
        self.model = get_class_by_column(self.col)
        self.stmt = select(self.model)

    def get_backref(self, model):
        self.rel_attr = get_backref(self.model, model)

    def toggleChip(self, e, data_item, parent_element, session):
        expand = e.sender.toggle()
        if len(parent_element.default_slot.children) > 1:
            parent_element.remove(1)
        if expand:
            with parent_element:
                with ui.row().classes('w-full grow'):
                    ui.space()
                    for pk in get_pk_names(data_item):
                        filter = self.col == getattr(data_item, pk)
                        filter = filter & filter if filter else filter
                    if self.stmt is not None:
                        stmt = self.stmt.where(filter)
                        stmt = select(self.model).from_statement(stmt)
                    else:
                        stmt = select(self.model).join.where(filter)
                    nice_alchemy.ItemList(self.label,
                                          self.model,
                                          field_list=self,
                                          session=session,
                                          stmt=stmt,
                                          parent=data_item).classes('on-right')

    def create_element(self, element_row, data_row, session, backref=None, parent_element=None):
        if backref:
            get_backref(backref)

        ChipToggle(self.label,
                   color='LightGray',
                   icon='arrow_right',
                   alt_icon='arrow_drop_down',
                   on_click=lambda e, i=data_row, p=parent_element, s=session: self.toggleChip(e, i, p, s))


def create_filter_stmt(stmt, data_row, fields):
    # filter = select(parent)
    count = 0
    for field in fields:
        if isinstance(field, Value):
            if getattr(data_row, field.col_prop):
                stmt = stmt.where(field.col.like(f'%{getattr(data_row, field.col_prop)}%'))
                count += 1
                # stmt = stmt.where(field.col == getattr(data_row, field.col_prop))
        elif isinstance(field, RelationPaired):

            join, jcount = create_filter_stmt(stmt.join(get_model_from_row(getattr(data_row, field.rel_attr))),
                                              getattr(data_row, field.rel_attr), field.fields)

            if jcount:
                stmt = join
                count += 1

        elif isinstance(field, RelationSingle):
            if getattr(data_row, field.col_prop):
                # print('single_prop', int(getattr(data_row, field.col_prop)))
                stmt = stmt.where(field.col == getattr(data_row, field.col_prop))
                count += 1

    return stmt, count
