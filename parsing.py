import csv

from database import Transaction


def parse_csv(csv_file_io):
    transaction_list = []
    reader = csv.reader(csv_file_io)
    for line_num, line in enumerate(reader):
        try:
            transaction = parse_line(line)
        except ValueError:
            if line_num != 0:
                # Sometimes, the first line is the heading. If casting to float
                # fails on another line, though, raise the error.
                print(f"Exception in line {line_num}: {line}")
                raise
        except Exception:
            print(f"Exception in line {line_num}: {line}")
            raise
        else:
            if transaction is not None:
                transaction_list.append(transaction)
    return transaction_list


def parse_line(csv_line):
    assert isinstance(csv_line, list)
    if len(csv_line) == 4:
        # CIBC
        name = csv_line[1]
        for match_string in [
            "Internet Banking INTERNET TRANSFER",
            "Internet Banking INTERNET BILL PAY",
            "Electronic Funds Transfer PAY",
            "Point of Sale - Interac RETAIL PURCHASE",
        ]:
            if name.startswith(match_string):
                name = remove_transaction_number(name, match_string)
        return Transaction(
            date=csv_line[0],
            name=name,
            amount=string_to_float(csv_line[2]) - string_to_float(csv_line[3]),
        )
    if len(csv_line) == 5:
        if csv_line[4] == "SPREADSHEET":
            # Rogers Mastercard from spreadsheet
            return Transaction(
                date=csv_line[0],
                name=csv_line[2],
                amount=string_to_float(csv_line[4]),
            )
        else:
            # CIBC Visa
            return Transaction(
                date=csv_line[0],
                name=csv_line[1],
                amount=string_to_float(csv_line[2])
                - string_to_float(csv_line[3]),
            )
    if len(csv_line) == 12:
        # Rogers Mastercard
        return Transaction(
            date=csv_line[0],
            name=csv_line[7],
            amount=string_to_float(csv_line[11]),
        )
    return None


def remove_transaction_number(name, match_string):
    """
    Some CIBC transactions have a unique number in the name, making categorizing
    by name impractical. Remove this number.
    """
    assert name.startswith(match_string)
    n_words = len(match_string.split(" "))
    transaction_number = name.split(" ")[n_words]
    return name.replace(transaction_number, "__REDACTED_TRANSACTION_NUMBER__")


def string_to_float(string):
    if string == "":
        return 0.0
    return float(string.replace("$", "").replace(",", ""))
