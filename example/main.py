from nicegui import app, ui, binding
from nice_alchemy import Field, Relation, Value, FilterableField, RelationPaired, RelationSingle, RelationList, set_model_base, set_sessionmaker
from nice_alchemy import FieldList, ItemList
import models
import us

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database

engine = sqlalchemy.create_engine(f'sqlite:///example.db', echo=False, isolation_level="AUTOCOMMIT")
if not database_exists(engine.url):
    create_database(engine.url)

set_sessionmaker(sessionmaker(engine, expire_on_commit=False))
set_model_base(models.Base)
models.Base.metadata.create_all(engine)


class DateTimePicker(ui.input):
    date = binding.BindableProperty()
    time = binding.BindableProperty()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.date = ''
        self.time = ''
        with self:
            with ui.menu().props('no-parent-event') as date:
                with ui.date().bind_value(self, 'date'):
                    with ui.row().classes('justify-end'):
                        ui.button('Close', on_click=date.close).props('flat')

            with ui.menu().props('no-parent-event') as time:
                with ui.time().bind_value(self, 'time'):
                    with ui.row().classes('justify-end'):
                        ui.button('Close', on_click=time.close).props('flat')

            with self.add_slot('append'):
                ui.icon('event').on('click', date.open).classes('cursor-pointer')
                ui.icon('access_time').on('click', time.open).classes('cursor-pointer')
        self.bind_value(self, 'date', forward=lambda v: self.parse_date(v), backward=lambda v: self.set_date(v))

        self.bind_value(self, 'time', forward=lambda v: self.parse_time(v), backward=lambda v: self.set_time(v))

    def parse_date(self, v):
        if isinstance(v, str):
            result = list(filter(None, v.split()))
            if len(result) > 0:
                return result[0]
        return ''

    def parse_time(self, v):
        if isinstance(v, str):
            result = list(filter(None, v.split()))
            if len(result) > 1:
                return result[1]
        return ''

    def set_date(self, v):
        return f'{v} {self.time}'

    def set_time(self, v):
        return f'{self.date} {v}'


@ui.page('/')
def index():
    ui.link('Employees', employees_page)
    ui.link('Locations', locations_page)
    ui.link('Shifts', shifts_page)


@ui.page('/employees')
def employees_page():
    ui.link('Home', index)

    with FieldList() as employees:
        with RelationPaired('', col=models.Employee.user_id):
            Value('Name', models.User.name)
            with RelationList(label='Address', col=models.UserAddress.user_id):
                with RelationPaired('', col=models.UserAddress.address_id):
                    Value('Street', models.Address.street)
                    Value('City', models.Address.city)
                    RelationSingle('State', models.Address.state, options=[state.name for state in us.states.STATES])
        RelationSingle(
            'Location',
            col=models.Employee.location_id,
            relation_chain='Location.name',
        )
    ItemList("Employees", models.Employee, field_list=employees)


@ui.page('/locations')
def locations_page():
    ui.link('Home', index)

    with FieldList() as locations:
        Value('Name', models.Location.name)
        with RelationPaired(label='Location Address', col=models.Location.address_id):
            Value('Street', models.Address.street)
            Value('City', models.Address.city)
            RelationSingle('State', models.Address.state, options=[state.name for state in us.states.STATES])

    ItemList("Location", models.Location, field_list=locations)


@ui.page('/shifts')
def shifts_page():
    ui.link('Home', index)

    with FieldList() as employee_shifts:
        RelationSingle('Employee', col=models.EmployeeShift.employee_id, relation_chain='Employee.user.name')
        Value('Clock In', models.EmployeeShift.clock_in, type=DateTimePicker)
        Value('Clock Out', models.EmployeeShift.clock_out, type=DateTimePicker)

    ItemList("Shifts", models.EmployeeShift, field_list=employee_shifts)


ui.run()
