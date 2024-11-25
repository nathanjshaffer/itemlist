"""
list database rows using sqlalchemy models
"""

from nicegui import app, ui
from sqlalchemy import select
from dataclasses import dataclass, field
import operator

from pprint import pprint

unique_index = 0


def get_unique_id():
    unique_index += 1
    return unique_index


def get_model_from_row(row):
    return row.__class__._sa_class_manager.class_


def get_pk_names(row):
    return [pk_column.name for pk_column in row.__class__.__table__.primary_key.columns.values()]


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
class Parent():
    col: str
    rel_attr: str
    parent_item: object


@dataclass
class ValueExpression:
    field: object
    op: object
    val: object


class Field():
    def __init__(self, *args, **kwargs):
        self.super.__init__(*args, **kwargs)
        self.FIELD_ID = get_unique_id()

    def __eq__(self, value):
        return ValueExpression(self, operator.eq, value)


@dataclass
class Value(Field):
    label: str
    col: str
    type: object = ui.input


@dataclass
class Relation(Field):
    label: str  # Label for relationship
    fk_col: str  # foreign key or backref column in base model
    fk_model: object  # model for relationship


@dataclass
class RelationPaired(Relation):  # 1:1 relationship
    # label: str  # Label for relationship
    # fk_col: str  # foreign key or backref column in base model
    # fk_model: object  # model for relationship
    pk_col: str = None  # referenced column for foreign key
    rel_attr: str = None
    fields: list = None


@dataclass
class RelationSingle(Relation):  # m:1 relationship
    # label: str  # Label for relationship
    # fk_col: str  # foreign key or backref column in base model
    # fk_model: object  # model for relationship
    pk_col: str  # referenced column for foreign key
    relation_chain: str
    filter: list = field(default_factory=lambda: [])


@dataclass
class RelationList(Relation):  # m:m relationship
    # label: str  # Label for relationship
    # fk_model: object  # model for relationship
    # fk_col: str
    rel_attr: str
    filter: list = field(default_factory=lambda: [])
    fields: list = None


class ItemList(ui.card):
    def addRefreshItem(self, model, refreshable):
        if type(refreshable) == ui.refreshable:
            if not isinstance(model, str):
                model = model.__name__
            if model not in app.storage.client['refresh_model_list'].keys():
                app.storage.client['refresh_model_list'][model] = {}

            # refreshable = (self, refreshable.func.__name__)
            app.storage.client['refresh_model_list'][model][self] = refreshable.func.__name__

            if model not in self.refresh_model_list:
                self.refresh_model_list.append(model)

    def refresh_models(self):
        refreshed = []
        pprint(app.storage.client['refresh_model_list'])
        for model in self.refresh_model_list:
            for key, refreshable in app.storage.client['refresh_model_list'][model].items():
                func = getattr(key, refreshable)
                if key not in refreshed and hasattr(func, 'refresh'):
                    refreshed.append(key)
                    func.refresh()

    def __init__(self, db, label, model, fields, parents=[], filter=[], on_edit=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'refresh_model_list' not in app.storage.client:
            app.storage.client['refresh_model_list'] = {}
        self.refresh_model_list = []
        self.listName = label
        self.model = model
        self.db = db
        self.input_fields = fields
        self.input_elements = {}
        self.createItemRow = None
        self.filter = list(filter)
        self.on_edit = on_edit
        self.select_box_options = {}
        self.parents = list(parents)
        for parent in parents:
            for pk in get_pk_names(parent.parent_item):
                self.filter.append(getattr(model, parent.col) == getattr(parent.parent_item, pk))
                pprint(self.filter[0].__dict__['left'].__dict__)

        # print('\nfilter: ', self.filter)
        with self:
            self.createList()

    def toggleChip(self, e, item):
        expand = e.sender.toggle()
        if len(e.sender.list_row_container.default_slot.children) > 1:
            e.sender.list_row_container.remove(1)
        print(expand)
        print(e.sender.rel.filter)
        if expand:
            with e.sender.list_row_container:
                with ui.row().classes('w-full grow'):
                    ui.space()
                    rel = e.sender.rel
                    print(rel.fk_col, rel.rel_attr, item)
                    ItemList(self.db,
                             rel.label,
                             rel.fk_model,
                             rel.fields,
                             parents=[Parent(rel.fk_col, rel.rel_attr, item)],
                             filter=rel.filter).classes('on-right')

    @ui.refreshable
    def createList(self):
        def update_list__options(field, element, model, column, value = None):
            stmt = select(field.fk_model)
            if value &:
                stmt = stmt.where(column = value)
            option_items = session.scalars(stmt).all()
            options = {}
            for item in option_items:
                label = operator.attrgetter(field.relation_chain)(item)
                options[getattr(item, field.pk_col)] = label
            element.set_options(options)
            return options

        def process_input_fields(fields):
            for field in fields:
                if isinstance(field, Value):
                    self.input_elements[field.col] = field.type(field.label).on('keydown.enter', self.createItem)
                elif isinstance(field, RelationPaired):
                    self.addRefreshItem(field.fk_model, self.createList)
                    process_input_fields(field.fields)

                elif isinstance(field, RelationSingle):
                    self.addRefreshItem(field.fk_model, self.createList)
                    self.input_elements[field.fk_col] = ui.select(label=field.label, with_input=True)

                    if field.filter:
                        if isinstance(field.filter, ValueExpression):
                            filter = ValueExpression
                    update_list__options(field, self.input_elements[field.fk_col], field.fk_model, )
                    stmt = select(field.fk_model)



                        stmt = stmt.where(field.filter)
                    option_items = session.scalars(stmt).all()

                    options = {}
                    for item in option_items:
                        # attr = item
                        # for rel in field.relation_chain:
                        #     getattr(attr, rel)
                        label = operator.attrgetter(field.relation_chain)(item)
                        options[getattr(item, field.pk_col)] = label

                    self.select_box_options[field.label] = options


                elif isinstance(field, RelationList):
                    pass

        def process_row_fields(item, fields, list_row_container):
            for field in fields:
                if isinstance(field, Value):
                    field.type(field.label).bind_value(item, field.col).on('keydown.enter',
                                                                           lambda i=item: self.saveItem(i))
                elif isinstance(field, RelationPaired):
                    process_row_fields(getattr(item, field.rel_attr), field.fields, list_row_container)
                elif isinstance(field, RelationSingle):
                    ui.select(label=field.label, options=self.select_box_options[field.label]).bind_value(
                        item, field.fk_col).on('keydown.enter', lambda i=item: self.saveItem(i))

                elif isinstance(field, RelationList):
                    chip = ChipToggle(field.label,
                                      color='LightGray',
                                      icon='arrow_right',
                                      alt_icon='arrow_drop_down',
                                      on_click=lambda e, i=item: self.toggleChip(e, i))
                    chip.list_row_container = list_row_container
                    chip.rel = field

        with self.db.Session() as session:

            select_box_options = {}
            self.addRefreshItem(self.model, self.createList)
            stmt = select(self.model)
            # for join in self.joins.keys():
            #     stmt.join(getattr(modelModule, join))

            if self.filter:
                stmt = stmt.where(*self.filter)
            items = session.scalars(stmt).all()
            if self.filter:
                print('stmt', stmt)
                print('items', items)
            # print('filter', self.filter)

            with ui.card():
                self.createItemRow = ui.row().classes('center')
                with self.createItemRow:
                    ui.label(self.listName)
                    process_input_fields(self.input_fields)

                    ui.button(on_click=lambda: self.createItem(), icon='add').props('flat').classes('ml-auto')
            for item in items:
                with ui.column().classes('w-full grow') as list_row_container:
                    with ui.row().classes('items-center'):
                        process_row_fields(item, self.input_fields, list_row_container)
                        ui.button(icon='delete', on_click=lambda i=item: self.deleteItem(i)).props('flat')
                        ui.button(icon='edit', on_click=lambda i=item: self.on_edit(i)).props('flat')

    def createItem(self):
        with self.db.Session() as session:
            session.expire_on_commit = False

            def process_field(field, values):
                if isinstance(field, Value):
                    values[field.col] = self.input_elements[field.col].value
                elif isinstance(field, RelationPaired):
                    join_item = process_fields(field.fields, field.fk_model)
                    values[field.fk_col] = getattr(join_item, field.pk_col)
                    # print(values)
                elif isinstance(field, RelationSingle):
                    values[field.fk_col] = self.input_elements[field.fk_col].value

            def process_fields(fields, model, parents=[]):
                values = {}
                for parent in parents:
                    values[parent.rel_attr] = parent.parent_item
                for field in fields:
                    process_field(field, values)

                print(values)
                item = model(**values)
                session.add(item)
                session.commit()
                return item

            process_fields(self.input_fields, self.model, self.parents)

            session.commit()

        self.refresh_models()

    def deleteItem(self, item) -> None:
        with self.db.Session() as session:

            model = get_model_from_row(item)
            filters = []
            for pk in get_pk_names(item):
                filters.append(getattr(model, pk) == getattr(item, pk))
            session.query(model).filter(*filters).delete()
            # session.delete(item)
            session.commit()

        self.refresh_models()

    def saveItem(self, item):
        self.db.saveData(item)
        self.refresh_models()
