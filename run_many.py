import subprocess
import calendar

RATE = 200
RETAINER = 1000
YEAR = 2023

total_sum = 0

for month_num in range(12):
    month_num += 1
    month_name = calendar.month_name[month_num]
    start_date = f"{YEAR}-{month_num:02d}-01"
    _, last_day = calendar.monthrange(YEAR, month_num)
    end_date = f"{YEAR}-{month_num:02d}-{last_day}"
    filename = f"{YEAR}-{month_num:02d}_{month_name}"

    with open('template', 'r') as template_file:
        template = template_file.read()

    command = f'jh ../journal {start_date} {end_date} --rate={RATE} --retainer={RETAINER}'
    print(command)
    command_result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    command_output = command_result.stdout.decode()
    if command_result.returncode != 0:
        print(command_output)
        break

    with open(filename, 'w') as output_file:
        output_file.write(template)
        output_file.write(command_output)

    try:
        last_line = command_output.splitlines()[-1]
        number = float(last_line.split('$')[-1].strip())
        total_sum += number
    except ValueError:
        print(f"Could not parse number from the last line of {filename}")

print(f"Total sum: ${total_sum:.2f}")

