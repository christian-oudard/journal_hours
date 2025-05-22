#! /usr/bin/env python3

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta

DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M'
DISPLAY_TIME_FORMAT = '%I:%M %p'

SHOW_INTERVALS = False
SHOW_DAILY_EARNINGS = False


class IntervalError(ValueError):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--rate', type=int)
    parser.add_argument('--average', action='store_true')
    parser.add_argument('--retainer', type=int)
    parser.add_argument('journal_file')
    parser.add_argument('start', nargs='?')
    parser.add_argument('end', nargs='?')
    args = parser.parse_args()

    # Parse start and end dates if they are given (inclusive date range).
    # If no end date is given, use all available intervals.
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if end_date is None:
        end_date = date.today()

    if start_date is None and args.start is not None:
        print('Invalid start date: {}'.format(args.start), file=sys.stderr)
        sys.exit(1)
    if end_date is None and args.end is not None:
        print('Invalid end date: {}'.format(args.end), file=sys.stderr)
        sys.exit(1)
    if start_date is not None and end_date < start_date:
        print('End date must be after start date.', file=sys.stderr)
        sys.exit(1)

    # Process journal file.
    with open(args.journal_file) as f:
        lines = [ l.strip() for l in f.readlines() ]

    intervals_by_date = process(lines)
    intervals_by_date = [
        (d, intervals)
        for (d, intervals) in intervals_by_date
        if (
            len(intervals) > 0
            and (start_date is None or d >= start_date)
            and (end_date is None or d <= end_date)
        )
    ]

    # Fill start date if it is not given.
    if start_date is None:
        if len(intervals_by_date) == 0:
            raise ValueError('No intervals found.')
        start_date = intervals_by_date[0][0]

    # Create JSON output if requested.
    if args.json:
        json_data = {}
        for (d, intervals) in intervals_by_date:
            json_data[force_timestamp(d)] = [
                (force_timestamp(start), force_timestamp(end))
                for (start, end) in intervals
            ]
        print(json.dumps(json_data))
        return

    if start_date is not None:
        print('Dates: {} to {}'.format(
            start_date.strftime(DATE_FORMAT),
            end_date.strftime(DATE_FORMAT),
        ))

    # Print out results.
    all_intervals = []
    out_lines = []
    for (d, intervals) in intervals_by_date:
        all_intervals.extend(intervals)
        elapsed = interval_sum(intervals)

        out_line = '    {}: {}'.format(
            d.strftime(DATE_FORMAT),
            format_timedelta(elapsed),
        )
        if args.rate is not None and SHOW_DAILY_EARNINGS:
            hours = elapsed.total_seconds() / (60 * 60)
            amount = hours * args.rate
            out_line += ' {:>8}'.format('${:.2f}'.format(amount))

        out_lines.append(out_line)

        if SHOW_INTERVALS:
            for (start, end) in intervals:
                out_lines.append('      {} - {}'.format(
                    start.strftime(DISPLAY_TIME_FORMAT),
                    end.strftime(DISPLAY_TIME_FORMAT),
                ))

    total_elapsed = interval_sum(all_intervals)
    total_hours = total_elapsed.total_seconds() / (60 * 60)
    if total_elapsed == timedelta(0):
        print('No hours recorded.')
        sys.exit(1)

    print()
    print('Hours worked:')
    for line in out_lines:
        print(line)
    print()
    print('Total time worked: {:.2f} hours ({})'.format(total_hours, format_timedelta(total_elapsed)))

    total_due = None
    if args.rate is not None:
        print('Hourly rate: ${}'.format(args.rate))
        total_due = total_hours * args.rate

    if args.retainer:
        print('Gross total: ${:.2f}'.format(total_due))
        print('Already-paid monthly retainer: ${}'.format(args.retainer))
        total_due = max(0, total_due - args.retainer)

    if args.average and start_date is not None:
        days = (end_date - start_date).days + 1
        weeks = days / 7
        average = total_elapsed / weeks
        print('Average hours per week: {:.2f} ({})'.format(average.total_seconds() / (60 * 60), format_timedelta(average)))

    if total_due is not None:
        print('Total due: ${:.2f}'.format(total_due))


def process(lines):
    current_date = None
    current_interval = []
    intervals_by_date = []  # [(current_date, [(start, end)])]

    for (line_number, line) in enumerate(lines):
        line = line.strip()

        # Try to find a date.
        d = parse_date(line)
        if d is not None:
            current_date = d
            if len(intervals_by_date) > 0 and current_date <= intervals_by_date[-1][0]:
                raise IntervalError('On line {}, the date {} was out of order.'.format(line_number, d.strftime(DATE_FORMAT)))
            intervals_by_date.append((current_date, []))

        # Try to find a start or finish time.
        time_result = parse_time(line, current_date)
        if time_result is None:
            continue

        # Ensure that each timestamp is part of a pair.
        action, t = time_result
        if action == 'start':
            if len(current_interval) == 0:
                current_interval.append(t)
            else:
                raise IntervalError('On line {}, found unexpected interval start.'.format(line_number))
        elif action == 'end':
            if len(current_interval) == 1:
                current_interval.append(t)
                if current_interval[0] > current_interval[1]:  # Sometimes I work past midnight.
                    current_interval[1] += timedelta(days=1)
                intervals_by_date[-1][1].append(tuple(current_interval))
                current_interval = []
            else:
                raise IntervalError('On line {}, found unexpected interval end.'.format(line_number))

    # If the ending interval is open and on the current day, simulate closing the interval right now.
    if len(current_interval) == 1:
        if current_date == date.today():
            now = datetime.now()
            if current_interval[0] < now:
                current_interval.append(now)
                intervals_by_date[-1][1].append(tuple(current_interval))

    return intervals_by_date


def parse_time(line, current_date):
    if ' ' not in line:
        return None

    action, time_string = line.split(' ', 1)
    if action not in ['start', 'end']:
        return None

    try:
        t = time.strptime(time_string, TIME_FORMAT)
    except ValueError:
        return None

    if current_date is None:
        raise IntervalError('Found interval start before any date markers.')

    t = assemble_datetime(current_date, t)
    return (action, t)


def interval_sum(intervals):
    total = timedelta()
    for (start, end) in intervals:
        total += end - start
    return total


def format_timedelta(td):
    hours, rem = divmod(td.total_seconds(), (60 * 60))
    minutes, seconds_ = divmod(rem, 60)
    return '{}h{:02d}m'.format(round(hours), round(minutes))


def parse_date(s):
    try:
        return force_date(datetime.strptime(s, DATE_FORMAT))
    except (TypeError, ValueError):
        return None


def force_date(d):
    """Turn a date or a datetime into a date."""
    return date(d.year, d.month, d.day)


def force_timestamp(d):
    return int(time.mktime(d.timetuple()))


def assemble_datetime(d, t):
    """Make a datetime out of a date and a time. Ignores seconds and microseconds."""
    return datetime(d.year, d.month, d.day, t.tm_hour, minute=t.tm_min)


def flatten(list_of_lists):
    for sublist in list_of_lists:
        for item in sublist:
            yield item



if __name__ == '__main__':
    main()
