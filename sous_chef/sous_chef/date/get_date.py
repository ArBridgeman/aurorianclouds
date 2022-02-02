import datetime

# TODO no built-in methods for this in python?
# TODO move to config
DESIRED_MEAL_TIMES = {"morning": "8:30", "evening": "18:15"}
DAYS_OF_WEEK = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def get_anchor_date(weekday_index):
    today = datetime.datetime.today()
    return today + datetime.timedelta(
        days=max(0, weekday_index - today.weekday())
    )


def get_due_date(
    day, anchor_date=get_anchor_date(4), hour=0, minute=0, second=0
):
    """
    Transfer day to proper due date. Use the week after given anchor date.
    :param day: weekday in int (monday: 0) or str.
    :param anchor_date: anchor date to set day before specified week.
    :param hour: hour of datetime
    :param minute: minute of datetime
    :param second: second of datetime
    :return:
    """
    # TODO make clearer what doing and cleaner code
    # TODO does anchor_date need to be a variable?
    if isinstance(day, str):
        day = DAYS_OF_WEEK.index(day.lower())

    new_date = anchor_date + datetime.timedelta(
        days=(day - anchor_date.weekday() + 7) % 7
    )
    if new_date.date() == anchor_date.date():
        new_date = new_date + datetime.timedelta(days=7)

    new_date = new_date.replace(
        hour=int(hour), minute=int(minute), second=int(second)
    )

    return new_date
