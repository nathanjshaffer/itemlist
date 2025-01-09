"""
list database rows using sqlalchemy models
"""

from nicegui import ui, app
from nicegui.elements.mixins.icon_element import IconElement
from sqlalchemy import select, inspect, bindparam
from dataclasses import dataclass, KW_ONLY, field
import operator
from sqlalchemy_utils import get_class_by_table

from pprint import pprint

import nice_alchemy.context as context

from nice_alchemy.fields import ChipToggle, Field, Relation, Value, FilterableField, RelationPaired, RelationSingle, RelationList
from nice_alchemy.fields import get_sessionmaker, get_pk_names, get_class_by_column, create_filter_stmt


class ItemList(ui.card):
    def __init__(self, label, model, *args, session=None, field_list=None, filter=None, parent_row=None, **kwargs):
        ui.card.__init__(self, **kwargs)

        self.listName = label
        self.model = model
        self.session = session
        self.field_list = field_list
        self.filter_stmt = filter
        self.parent = parent_row

        self.db = get_sessionmaker()

        if 'refresh_model_list' not in app.storage.client:
            app.storage.client['refresh_model_list'] = {}
        self.refresh_model_list = []

        # ui dropdown filter selection
        self.filter_elements = {}
        filter_row = None
        self.ui_filter_stmt = None

        if self.filter_stmt is None:
            self.filter_stmt = select(self.model)

        # data creation elements
        self.create_item_ui_row = None
        self.create_item_row = None
        self.create_item_elements = {}

        # data editing elements

        self.select_box_options = {}
        # list of modified rows
        self.modified = {}

        with self:
            self.create_filter_ui()
            self.createList()

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

    def create_filter_ui(self):
        @ui.refreshable
        def create_fields():
            with self.db() as session:
                self.process_input_fields(self.filter_elements, self.filter_row, self.filter_row,
                                          self.field_list.fields, session)

        def create_filter():
            filter, count = create_filter_stmt(select(self.model), self.filter_row, self.field_list.fields)
            if count:
                self.ui_filter_stmt = filter
            self.createList.refresh()
            self.filter_icon.set_name('filter_list')

        def clear_filter():
            self.ui_filter_stmt = None
            self.createList.refresh()
            self.filter_icon.set_name('filter_list_off')
            self.filter_row = self.model()
            create_fields.refresh()

        with ui.row() as head:
            ui.label(self.listName)
            ui.space()

            def toggle():
                self.filter_menu.set_visibility(not self.filter_menu.visible)

            self.filter_icon = ui.icon('filter_list_off').on('click', toggle).classes('cursor-pointer')
            with ui.card() as self.filter_menu:
                with ui.row():
                    self.filter_row = self.model()
                    create_fields()
                with ui.row().classes('justify-end'):
                    ui.button('Close', on_click=toggle).props('flat')
                    ui.button('Filter', on_click=create_filter).props('flat')
                    ui.button('Clear', on_click=clear_filter).props('flat')
            self.filter_menu.set_visibility(False)
        ui.separator()

    def process_input_fields(self, element_row, root, data_row, fields, session):
        for field in fields:
            field.create(element_row,
                         data_row,
                         backref=self.model,
                         session=session,
                         event_handlers=[('keydown.enter', lambda f=field: self.createItem(f))])

            if isinstance(field, RelationPaired):
                self.process_input_fields(element_row, root, getattr(data_row, field.rel_attr), field.fields,
                                          self.session)
                self.addRefreshItem(field.model, self.createList)

            elif isinstance(field, RelationSingle):
                self.addRefreshItem(field.model, self.createList)


    @ui.refreshable
    def createList(self):
        def process_row_fields(root, data_row, fields, list_row_container):
            def modify_row():
                self.modified[id(root)] = (root, list_row_container.save_btn)
                list_row_container.save_btn.enable()

            row_elements = {}
            for field in fields:
                field.create_row_editor_element(row_elements,
                                     data_row,
                                     session=self.session,
                                     parent_element=list_row_container,
                                     event_handlers=[('keydown.enter', lambda i=root: self.saveItem(i)),
                                                     ('update:modelValue', modify_row)])

                #
                # if isinstance(field, Value):
                #     field.create_row_editor_element(row_elements,
                #                          data_row,
                #                          event_handlers=[('keydown.enter', lambda i=root: self.saveItem(i)),
                #                                          ('update:modelValue', modify_row)])

                if isinstance(field, RelationPaired):
                    # print(data_row)
                    att_item = getattr(data_row, field.rel_attr)
                    if att_item:
                        process_row_fields(root, att_item, field.fields, list_row_container)

                # elif isinstance(field, RelationSingle):
                #     field.create_row_editor_element(row_elements,
                #                          data_row,
                #                          self.session,
                #                          event_handlers=[('update:modelValue', modify_row)])
                #
                # elif isinstance(field, RelationList):
                #     field.create_row_editor_element(row_elements, data_row, self.session, parent_element=list_row_container)

        if not self.session:
            self.session = self.db()
        with self.session:
            self.addRefreshItem(self.model, self.createList)
            stmt = self.filter_stmt
            if self.ui_filter_stmt is not None:
                stmt = stmt.intersect(self.ui_filter_stmt)
                stmt = select(self.model).from_statement(stmt)

            items = self.session.scalars(stmt).all()
            self.session.commit()
            with ui.card():
                ui.label('Create New')
                self.create_item_ui_row = ui.row().classes('center')
                with self.create_item_ui_row:

                    self.create_item_row = self.model()
                    if self.parent:
                        setattr(self.create_item_row, self.field_list.col_prop,
                                getattr(self.parent,
                                        get_pk_names(self.parent)[0]))
                    self.process_input_fields(self.create_item_elements, self.create_item_row, self.create_item_row,
                                              self.field_list.fields, self.session)

                    ui.button(on_click=lambda: self.createItem(), icon='add').props('flat').classes('ml-auto')
            for data_row in items:
                with ui.column().classes('w-full grow') as list_row_container:
                    with ui.row().classes('items-center'):
                        process_row_fields(data_row, data_row, self.field_list.fields, list_row_container)
                        ui.button(icon='delete', on_click=lambda i=data_row: self.deleteItem(i)).props('flat')
                        list_row_container.save_btn = ui.button(icon='save',
                                                                on_click=lambda: self.save_modified()).props('flat')
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

            process_fields(self.field_list.fields, self.create_item_row)

            session.commit()

        self.refresh_models()

    def deleteItem(self, data_row) -> None:
        with self.db() as session:
            session.delete(data_row)
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
            self.modified = {}
