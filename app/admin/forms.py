from flask_wtf import FlaskForm
from wtforms import DateField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, NumberRange, Optional, URL


class FamilyForm(FlaskForm):
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])


class StudentForm(FlaskForm):
    family_id = SelectField("Family", coerce=int, validators=[DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    grade = IntegerField("Grade (0=K)", validators=[DataRequired(), NumberRange(min=0, max=12)])
    teacher = StringField("Teacher", validators=[DataRequired()])


class SportForm(FlaskForm):
    name = StringField("Sport Name", validators=[DataRequired()])
    league = StringField("League", validators=[DataRequired()])
    league_website = StringField("League Website", validators=[Optional(), URL()])


class SportDateForm(FlaskForm):
    sport_id = SelectField("Sport", coerce=int, validators=[DataRequired()])
    event_name = StringField("Event Name", validators=[DataRequired()])
    event_description = TextAreaField("Description", validators=[Optional()])
    deadline = DateField("Deadline", validators=[DataRequired()])


class EmailTemplateForm(FlaskForm):
    scope = SelectField(
        "Scope",
        choices=[("global", "Global"), ("sport", "Sport"), ("event", "Event")],
        validators=[DataRequired()],
    )
    sport_id = SelectField("Sport (for sport/event scope)", coerce=str, validators=[Optional()])
    sport_date_id = SelectField("Event (for event scope)", coerce=str, validators=[Optional()])
    subject = StringField("Email Subject", validators=[DataRequired()])
    body_text = TextAreaField(
        "Email Body",
        validators=[DataRequired()],
        description=(
            "Available variables: {event_name} {event_description} {deadline} "
            "{sport_name} {league} {league_website} {family_last_name} {days_before}"
        ),
    )


class IntervalForm(FlaskForm):
    days_before = IntegerField(
        "Days Before Deadline",
        validators=[DataRequired(), NumberRange(min=1, max=365)],
    )
