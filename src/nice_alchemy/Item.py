from nicegui import ui
from sqlalchemy import select, inspect, bindparam
from dataclasses import dataclass, KW_ONLY, field
import operator
from sqlalchemy_utils import get_class_by_table

from pprint import pprint

import nice_alchemy.context as context

from nice_alchemy.fields import ChipToggle, Field, Relation, Value, FilterableField, RelationPaired, RelationSingle, RelationList
from nice_alchemy.fields import get_sessionmaker, get_pk_names, get_class_by_column


class Item(ui.card):
    def __init__(self,
                 label,
                 model,
                 *args,
                 session=None,
                 field_list=None,
                 stmt=None,
                 on_edit=None,
                 parent=None,
                 **kwargs):
        ui.card.__init__(self, **kwargs)
        self.field_list = field_list
        if 'refresh_model_list' not in app.storage.client:
            app.storage.client['refresh_model_list'] = {}
        self.refresh_model_list = []
        self.listName = label
        self.model = model
        self.db = get_sessionmaker()
        self.session = session
        self.input_elements = {}
        self.input_row = None
        self.createItemRow = None
        self.on_edit = on_edit
        self.select_box_options = {}
        self.stmt = stmt
        if self.stmt is None:
            self.stmt = select(self.model)
        self.parent = parent
        with self:
            self.createList()
        self.modified = {}

    def addRefreshItem(self, model, refreshable):
        if type(refreshable) == ui.refreshable:
            if not model:
                return
            if not isinstance(model, str):
                model = model.__name__
            if model not in app.storage.client['refresh_model_list'].keys():
                app.storage.client['refresh_model_list'][model] = {}

            app.storage.client['refresh_model_list'][model][self] = refreshable.func.__name__

            if model not in self.refresh_model_list:
                self.refresh_model_list.append(model)

    def refresh_models(self):
        refreshed = []
        for model in self.refresh_model_list:
            for key, refreshable in app.storage.client['refresh_model_list'][model].items():
                func = getattr(key, refreshable)
                if key not in refreshed and hasattr(func, 'refresh'):
                    refreshed.append(key)
                    func.refresh()

    @ui.refreshable
    def createList(self):
        def update_list__options(target_field, element, value=None):
            if hasattr(target_field, 'source'):
                target_field.source.set_source_field_value(value)

            if target_field.stmt is not None:
                stmt = select(target_field.model).from_statement(target_field.stmt)
            else:
                stmt = select(target_field.model)
            option_items = session.scalars(stmt).all()
            options = {}
            for item in option_items:
                label = operator.attrgetter(target_field.relation_chain.split('.', 1)[1])(item)
                options[getattr(item, get_pk_names(item)[0])] = label
            element.set_options(options)
            return options

        def process_input_fields(root, data_row, fields):
            for field in fields:
                if isinstance(field, Value):
                    field.create_element(self.input_elements,
                                         data_row,
                                         event_handlers=[('keydown.enter', lambda f=field: self.createItem(f))])

                elif isinstance(field, RelationPaired):
                    field.create_element(self.input_elements, data_row, backref=self.model)
                    process_input_fields(root, getattr(data_row, field.rel_attr), field.fields)
                    self.addRefreshItem(field.model, self.createList)

                elif isinstance(field, RelationSingle):
                    field.create_element(self.input_elements, data_row, self.session, backref = self.model)

                    self.addRefreshItem(field.model, self.createList)

                elif isinstance(field, RelationList):
                    field.get_backref(self.model)

        def process_row_fields(root, data_row, fields, list_row_container):
            def modify_row():
                self.modified[id(root)] = (root, list_row_container.save_btn)
                list_row_container.save_btn.enable()

            row_elements = {}
            for field in fields:
                if isinstance(field, Value):
                    field.create_element(row_elements,
                                         data_row,
                                         event_handlers=[('keydown.enter', lambda i=root: self.saveItem(i)),
                                         ('update:modelValue', modify_row)])

                elif isinstance(field, RelationPaired):
                    att_item = getattr(data_row, field.rel_attr)
                    if att_item:
                        process_row_fields(root, att_item, field.fields, list_row_container)

                elif isinstance(field, RelationSingle):
                    field.create_element(row_elements, data_row, self.session, event_handlers=[('update:modelValue', modify_row)])

                elif isinstance(field, RelationList):
                    field.create_element(row_elements, data_row, self.session, parent_element=list_row_container)

        if not self.session:
            self.session = self.db()
        with self.session:
            self.addRefreshItem(self.model, self.createList)
            items = self.session.scalars(self.stmt).all()
            with ui.card():
                self.createItemRow = ui.row().classes('center')
                with self.createItemRow:
                    ui.label(self.listName)
                    self.input_row = self.model()
                    if self.parent:
                        setattr(self.input_row, self.field_list.col_prop,
                                getattr(self.parent,
                                        get_pk_names(self.parent)[0]))
                    process_input_fields(self.input_row, self.input_row, self.field_list.fields)

                    ui.button(on_click=lambda: self.createItem(), icon='add').props('flat').classes('ml-auto')
            for data_row in items:
                with ui.column().classes('w-full grow') as list_row_container:
                    with ui.row().classes('items-center'):
                        process_row_fields(data_row, data_row, self.field_list.fields, list_row_container)
                        ui.button(icon='delete', on_click=lambda i=data_row: self.deleteItem(i)).props('flat')
                        list_row_container.save_btn = ui.button(icon='save', on_click=lambda: self.save_modified()).props('flat')
                        list_row_container.save_btn.disable()
            # self.session.commit()

    def createItem(self):
        with self.db() as session:
            session.expire_on_commit = False

            def process_field(field, data_row):
                if isinstance(field, RelationPaired):
                    att_item = getattr(data_row, field.rel_attr)

                    join_item = process_fields(field.fields, att_item)

            def process_fields(fields, data_row):

                for field in fields:
                    process_field(field, data_row)
                session.add(data_row)
                session.commit()

            process_fields(self.field_list.fields, self.input_row)

            session.commit()

        self.refresh_models()

    def deleteItem(self, data_row) -> None:
        with self.db() as session:

            model = get_model_from_row(data_row)
            filters = []
            for pk in get_pk_names(data_row):
                filters.append(getattr(model, pk) == getattr(data_row, pk))
            session.query(model).filter(*filters).delete()
            # session.delete(data_row)
            session.commit()

        self.refresh_models()

    def saveItem(self, data_row):
        with self.db() as session:
            session.expire_on_commit = False
            session.add(data_row)
            session.commit()
        self.refresh_models()

    def save_modified(self):
        with self.db() as session:
            session.expire_on_commit = False
            for key, row in self.modified.items():
                data_row, btn = row
                session.add(data_row)
                btn.disable()
            session.commit()
            self.modified={}
