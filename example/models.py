# coding: utf-8
from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from dataclasses import dataclass


class Base(DeclarativeBase):
  pass
metadata = Base.metadata



@dataclass
class Address(Base):
    __tablename__ = 'address'

    id : Mapped[int]
    id = mapped_column(Integer, primary_key=True)
    street : Mapped[str]
    street = mapped_column(Text)
    city : Mapped[str]
    city = mapped_column(Text)
    state : Mapped[str]
    state = mapped_column(Text)



@dataclass
class Employee(Base):
    __tablename__ = 'employee'

    id : Mapped[int]
    id = mapped_column(Integer, primary_key=True)
    user_id : Mapped[int]
    user_id = mapped_column(ForeignKey('user.id'))
    location_id : Mapped[int]
    location_id = mapped_column(ForeignKey('location.id'))

    location = relationship('Location', primaryjoin='Employee.location_id == Location.id', backref='employees')
    user = relationship('User', primaryjoin='Employee.user_id == User.id', backref='employees')



@dataclass
class EmployeeShift(Base):
    __tablename__ = 'employee_shift'

    id : Mapped[int]
    id = mapped_column(Integer, primary_key=True)
    clock_in : Mapped[int]
    clock_in = mapped_column(Integer, nullable=False)
    clock_out : Mapped[int]
    clock_out = mapped_column(Integer, nullable=False)
    employee_id : Mapped[int]
    employee_id = mapped_column(ForeignKey('employee.id'))

    employee = relationship('Employee', primaryjoin='EmployeeShift.employee_id == Employee.id', backref='employee_shifts')



@dataclass
class Location(Base):
    __tablename__ = 'location'

    id : Mapped[int]
    id = mapped_column(Integer, primary_key=True)
    name : Mapped[str]
    name = mapped_column(Text)
    address_id : Mapped[int]
    address_id = mapped_column(ForeignKey('address.id'))

    address = relationship('Address', primaryjoin='Location.address_id == Address.id', backref='locations')



@dataclass
class User(Base):
    __tablename__ = 'user'

    id : Mapped[int]
    id = mapped_column(Integer, primary_key=True)
    name : Mapped[str]
    name = mapped_column(Text)



@dataclass
class UserAddress(Base):
    __tablename__ = 'user_address'

    id : Mapped[int]
    id = mapped_column(Integer, primary_key=True)
    user_id : Mapped[int]
    user_id = mapped_column(ForeignKey('user.id'))
    address_id : Mapped[int]
    address_id = mapped_column(ForeignKey('address.id'))

    address = relationship('Address', primaryjoin='UserAddress.address_id == Address.id', backref='user_addresses')
    user = relationship('User', primaryjoin='UserAddress.user_id == User.id', backref='user_addresses')
