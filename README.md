# nice-alchemy

an attempt at creating a templating engine to connect nicegui elements to a datasource via sqlachemy

![Screenshot of ItemList](https://github.com/nathanjshaffer/nice-alchemy/blob/master/example/img/Itemlist_screenshot.png)

example app and database model is in the example directory

here is an example of usage for a set of data using the ItemList class:
```py
@ui.page('/employees')
def employees():
    ui.link('Home', index)

    with FieldList() as fields:
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
    ItemList("Employees", models.Employee, field_list=fields)
```

FieldList is a context manager to build template for the ItemList to query and edit data.

each child is a Field that defines a single or group of related database columns.  It should be noted that the relationships are not limited to a single table, but much more complex relationships can be defined and managed.

to use this nice-alchemy, take note of the following functions, set_model_base & set_sessionmaker:
```
class Base(sqlalchemy.orm.DeclarativeBase):
  pass

engine = sqlalchemy.create_engine(f'sqlite:///example.db)

# nice_alchemy needs to know what the base class is for sqlalchemy models
nice_alchemy.set_model_base(models.Base)
# set the global database session maker object fot nice_alchemy to access data
nice_alchemy.set_sessionmaker(sessionmaker(engine, expire_on_commit=False))
```py

## Field Types

  ### Value
    A single column that is definied by a value. 
    
    properties:
      label:  labe to display for field
      col: the column property of the sqlachemy model ex: User.name
      type: nicegui element class to generate default: ui.input
  ### RelationPaired
    Relation grouping for a one:one foreign key.  THis does not take care of any deleting/updating of the related row in the foreign table.  use triggers on the db server to accomplish.  
    This field type allows for editing related rows accross tables as if it were all in one table.
    
    Properties:
      label:  label to display for field(currently ignored)
      col: the column of the parent table that holds the foreign key to the related primary key.
        for example:
        ```py
        with FieldList() as employees:
          with RelationPaired('', col=models.Employee.user_id):
            Value('Name', models.User.name)
        ItemList(label="Employees", models.User, field_list=employees)
        ```
        The employees FieldList defines fields for the Employee table.  The column Employee.user_id has a foreign key constraint that relates to User.id.  By setting col=models.Employee.user_id, the child fields of RelationPaired will display the data for the User table. 
            
  ### RelationSingle
    A field that represents a namy:one relation allowing the user to select from a list of options.  This list by default will populate with a query of all current values in the database.  This can be filterable by argument, or filtered in response to a separated field updating.  Alternatively, a list of static options can be supplied to the template.
    
    Properties:
      label:  label to display for field
      col: the column property of the sqlachemy model ex: User.name
      relation_chain: the maodel property chain that defines the label to be displayed for the options.  this relies on sqlalchemy's backref.  for example if selecting fro a list of employees using Employee.id, you can have the name displayed in a dropdown box with relation_chain=Employee.user.name
      options: list of options if you wish to specify instead of populating from database
      
  ### RelationList
    Field that represents a one:many relationship.  Provides a dropdown table using ItemList to display.  Theoretically you could have infinit lists inside of lists, but that would probably start to cause some performance issues after a certain number of leveles.  for example, if you have a number of locations each with groups of employees assigned to them, this would allow to view and edit which employees are assigned to which location in the same location.

    Properties:
      label:  label to display for field
      col: the column property of the sqlachemy model.  For RelationList, this is the colum within table that contains the foreing key relating back to the primary key of the parent field.
        for example:
          ```py
          with FieldList() as users:
            with RelationList(label='Address', col=models.UserAddress.user_id):
            
          ItemList(label="Users", models.User, field_list=users)
          ```
           the users FieldList defines fields for the User table, and the UserAddress table has a foreignkey UserAddress.user_id that refers to User.id.  Therefore RelationList must define col=models.UserAddress.user_id
    
  


