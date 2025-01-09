
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database
from nicegui import app, ui, binding

# library to get state names
import us


from nice_alchemy import Value, RelationPaired, RelationSingle, RelationList, FieldList, ItemList, Static
import nice_alchemy
import models

engine = sqlalchemy.create_engine(f'sqlite:///example.db', echo=False, isolation_level="AUTOCOMMIT")
if not database_exists(engine.url):
    create_database(engine.url)

# nice_alchemy needs to know what the base class is for sqlalchemy models
nice_alchemy.set_model_base(models.Base)
# set the global database session maker object fot nice_alchemy to access data
nice_alchemy.set_sessionmaker(sessionmaker(engine, expire_on_commit=False))


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
        with RelationPaired(col=models.Employee.user_id):
            Static(label="lkasndflaj")
            Value(label='Name', col=models.User.name)
            with RelationList(label='Employee Address', col=models.UserAddress.user_id):
                with RelationPaired(col=models.UserAddress.address_id):
                    Value(label='Street',col=models.Address.street)
                    Value(label='City', col=models.Address.city)
                    RelationSingle(label='State', col=models.Address.state, options=[state.name for state in us.states.STATES])
        RelationSingle(
            label='Location',
            col=models.Employee.location_id,
            relation_chain='Location.name',
        )
    ItemList("Employees", models.Employee, field_list=employees)


@ui.page('/locations')
def locations_page():
    ui.link('Home', index)

    with FieldList() as locations:
        Value(label='Name', col=models.Location.name)
        with RelationPaired(col=models.Location.address_id):
            Value(label='Street',col=models.Address.street)
            Value(label='City', col=models.Address.city)
            RelationSingle(label='State', col=models.Address.state, options=[state.name for state in us.states.STATES])

    ItemList("Location", models.Location, field_list=locations)


@ui.page('/shifts')
def shifts_page():
    ui.link('Home', index)

    with FieldList() as employee_shifts:
        RelationSingle(label='Employee', col=models.EmployeeShift.employee_id, relation_chain='Employee.user.name')
        Value(label='Clock In', col=models.EmployeeShift.clock_in, type=DateTimePicker)
        Value(label='Clock Out', col=models.EmployeeShift.clock_out, type=DateTimePicker)

    ItemList("Shifts", models.EmployeeShift, field_list=employee_shifts)


ui.run()
