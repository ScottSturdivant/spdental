import os
import pytz
import boto3
from flask import Flask, render_template
from collections import OrderedDict
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.fields.html5 import DateTimeLocalField, EmailField, TelField
from wtforms.fields import TextAreaField
from wtforms.validators import DataRequired, InputRequired, Email
from datetime import datetime

tz = pytz.timezone('America/Denver')

# For jinja footer template
def now():
    return datetime.now(tz)

def get_year():
    return now().year

def get_weekday():
    return now().strftime('%A')

hours = OrderedDict()
hours['Monday'] = ('8:30', '3:00')
hours['Tuesday'] = ('8:30', '6:00')
hours['Wednesday'] = ('8:30', '3:00')
hours['Thursday'] = ('8:30', '6:00')
hours['Friday'] = (None, None)
hours['Saturday'] = (None, None)
hours['Sunday'] = (None, None)


def get_open_info(hours):
    now = datetime.now(tz)
    open_at, close_at = hours[get_weekday()]
    if open_at is None:
        return 'Closed for the weekend.  See you on Monday!'
    close_at = now.replace(hour=int(close_at.split(':')[0]) + 12)
    if now < close_at:
        return 'Open today until {} PM'.format(hours[get_weekday()][1])
    # Closed for the day.  When will they be open next?
    day, hours = find_next_opening(hours)
    return 'We have closed for today. We are open {0} at {1} AM.'.format(day, hours[0])


def find_next_opening(hours):
    today = get_weekday()
    start_search = False
    for day, hour_info in hours.items():
        if day == today:
            start_search = True
            continue
        if not start_search:
            continue

        open_at, close_at = hour_info
        if open_at:
            return day, hour_info
    return 'Monday', hours['Monday']


class AppointmentForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()], render_kw={'placeholder': 'Name*'})
    email = EmailField('Email', validators=[DataRequired(), Email()], render_kw={'placeholder': 'Email*'})
    phone = TelField('Phone', validators=[DataRequired()], render_kw={'placeholder': 'Phone*'})
    date = DateTimeLocalField('Preferred Date', format='%Y-%m-%dT%H:%M', validators=[InputRequired()])
    notes = TextAreaField('Notes',
        render_kw={
            'placeholder': 'What would you like to make an appointment for?'
        }
    )


app = Flask(__name__)
app.secret_key = os.urandom(128)
app.jinja_env.globals.update(get_year=get_year)
app.jinja_env.globals.update(get_weekday=get_weekday)
app.jinja_env.globals.update(hours=hours)
app.jinja_env.globals.update(get_open_info=get_open_info)


def handle_error(e):
    return render_template('errors/{}.html'.format(e.code)), e.code


if not app.debug:
    for e in [500, 404]:
        app.errorhandler(e)(handle_error)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/insurance/', methods=['GET'])
def insurance():
    return render_template('insurance.html')


@app.route('/sturdivant/', methods=['GET'])
def sturdivant():
    return render_template('sturdivant.html')


@app.route('/new_patients/', methods=['GET'])
def new_patients():
    return render_template('new_patients.html')


@app.route('/appointment/', methods=['GET', 'POST'])
def appointment():
    form = AppointmentForm()
    if form.validate_on_submit():
        from_email = os.environ.get('FROM_EMAIL', 'scott.sturdivant@gmail.com')
        to_email = os.environ.get('TO_EMAIL', 'scott.sturdivant@gmail.com')
        ses = boto3.client('ses')
        subject = 'New Appointment Request'
        message = render_template('email.msg', form=form)
        response = ses.send_email(
            Source=from_email,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {
                    'Data': subject,
                },
                'Body': {
                    'Html': {
                        'Data': message,
                    }
                }
            },
            ReplyToAddresses=[form.email.data],
            ReturnPath=from_email,
        )
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            return str(response)
        return render_template('appointment.html')
    return render_template('appointment.html', form=form)


if __name__ == '__main__':
    app.run()
