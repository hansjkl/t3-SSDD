from __future__ import annotations  # Solo lo dejo por si lo necesitan. Lo pueden eliminar
from sys import argv
import json
from read_file import parse_jsonc, parse_command

# Librerías adicionales por si las necesitan
# No son obligatorias y tampoco tienen que usarlas todas
# No puedes agregar ningún otro import que no esté en esta lista
import re
import os
import typing
import collections
import itertools
import dataclasses
import enum

# Recuerda que no se permite importar otros módulos/librerías a excepción de los creados
# por ustedes o las ya incluidas en este main.py

def forward_validation(transactions: dict, id: str) -> bool:
    for other in transactions:
        if other == id:
            continue
        if transactions[other]["status"] in ["ABIERTA", "EN_PREPARACION"]:
            for var_name in transactions[other]["reads"]:
                if var_name in transactions[id]["writes"]:
                    return False
    return True

def backward_validation(transactions: dict, id: str) -> bool:
    self_start = transactions[id]["order"]
    for other in transactions:
        if other == id:
            continue
        if (transactions[other]["commit_time"] > self_start):
            for var_name in transactions[other]["writes"]:
                if var_name in transactions[id]["reads"]:
                    return False
    return True

if __name__ == "__main__":
    # Completar con tu implementación o crea más archivos y funciones
    filepath = argv[1]
    data = parse_jsonc(filepath)
    filename = os.path.splitext(os.path.basename(filepath))[0]

    validation = data["VALIDATION"].strip().lower()
    validation_f = None
    if validation == "forward":
        validation_f = forward_validation
    else:
        validation_f = backward_validation
    servers = data["SERVERS"]
    global_db = data["DATA"]
    transaction_commands = data["TRANSACTIONS"]

    logs = []
    transactions = {}

    protected_vars = {}
    for server in servers:
        protected_vars[server] = {"read": {}, "write": {}}

    def free_protected_vars(id: str):
        for server in transactions[id]["servers"]:
            for var_name in transactions[id]["writes"]:
                if protected_vars[server]["write"][var_name] == 1:
                    protected_vars[server]["write"].pop(var_name)
                else:
                    protected_vars[server]["write"][var_name] -= 1

            for var_name in transactions[id]["reads"]:
                if protected_vars[server]["read"][var_name] == 1:
                    protected_vars[server]["read"].pop(var_name)
                else:
                    protected_vars[server]["read"][var_name] -= 1

    # Ejecutar comandos

    for command in transaction_commands:
        print()
        print(command)
        cmd_dict = parse_command(command)
        id = cmd_dict["id"]
        cmd = cmd_dict["command"]
        args = cmd_dict["args"]

        if cmd_dict["type"] == "T":

            if cmd == "BEGIN":
                if id not in transactions:
                    print("Inicia transacción")
                    transactions[id] = {"order": len(transactions), "status": "ABIERTA",
                                        "writes": {}, "reads": [], "servers": [], 
                                        "commit_time": -1}

            elif id not in transactions or transactions[id]["status"] in [
                "CONFIRMADA", "ABORTADA", "INVALIDA"]:
                print("Transacción inválida o ya no acepta comandos")
                continue

            elif cmd in ["READ", "WRITE"] and transactions[id]["status"] == "EN_PREPARACION":
                print("Acción inválida, se invalida transacción")
                transactions[id]["status"] = "INVALIDA"
                free_protected_vars(id)

            elif cmd == "READ":
                var_name = args[0]
                if (var_name in transactions[id]["writes"] and 
                    transactions[id]["writes"][var_name] != "DELETE"):
                    print("Lee transacción")
                    transactions[id]["reads"].append(var_name)
                elif var_name in global_db:
                    transactions[id]["reads"].append(var_name)
                    print("Lee global")
                else:
                    print("Lectura inválida, se cancela transacción")
                    transactions[id]["status"] = "INVALIDA"
            
            elif cmd == "WRITE":
                transactions[id]["writes"][args[0]] = args[1]

            elif cmd == "CAN_COMMIT":
                server = args[0]
                if server not in servers or server in transactions[id]["servers"]:
                    print("Servidor no existe o ya aceptó")
                    continue
                if not validation_f(transactions, id):
                    print("Falla validación")
                    if validation == "backward":
                        print("Backward, se aborta")
                        transactions[id]["status"] = "ABORTADA"
                        free_protected_vars(id)
                else:
                    conflict = False
                    for var_name in transactions[id]["writes"]:
                        if var_name in protected_vars[server]["read"]:
                            print(f"Conflicto con variable protegida {var_name}")
                            conflict = True
                            break
                    if conflict:
                        continue
                    for var_name in transactions[id]["reads"]:
                        if var_name in protected_vars[server]["write"]:
                            print(f"Conflicto con variable protegida {var_name}")
                            conflict = True
                            break
                    if conflict:
                        continue
                    # Acepta transacción
                    print(f"{server} acepta transacción.")
                    transactions[id]["status"] = "EN_PREPARACION"
                    transactions[id]["servers"].append(server)
                    for var_name in transactions[id]["writes"]:
                        if var_name in protected_vars[server]["write"]:
                            protected_vars[server]["write"][var_name] += 1
                        else:
                            protected_vars[server]["write"][var_name] = 1
                    for var_name in transactions[id]["reads"]:
                        if var_name in protected_vars[server]["read"]:
                            protected_vars[server]["read"][var_name] += 1
                        else:
                            protected_vars[server]["read"][var_name] = 1

            elif cmd == "ABORT":
                print("Abortada!")
                transactions[id]["status"] = "ABORTADA"
                free_protected_vars(id)
            
            elif cmd == "COMMIT":
                if not backward_validation(transactions, id):
                    print("Falla validación")
                    print("Backward, se aborta")
                    transactions[id]["status"] = "ABORTADA"
                    free_protected_vars(id)    
                    continue   
                if transactions[id]["status"] != "EN_PREPARACION":
                    print("Transacción no está EN_PREPARACION")
                    continue
                if len(transactions[id]["servers"]) <= len(servers)//2:
                    print("No hay quorum")
                    continue
                
                print("Transacción confirmada!")
                transactions[id]["status"] = "CONFIRMADA"
                transactions[id]["commit_time"] = len(transactions)
                free_protected_vars(id)
                for var_name in transactions[id]["writes"]:
                    val = transactions[id]["writes"][var_name]
                    if val == "DELETE":
                        if var_name in global_db:
                            global_db.pop(var_name)
                    else:
                        global_db[var_name] = val

                for other in transactions:
                    if other == id:
                        continue
                    if transactions[other]["status"] != "EN_PREPARACION":
                        continue
                    for other_read in transactions[other]["reads"]:
                        if other_read in transactions[id]["writes"]:
                            print(f"Abortando {other} por leer variable escrita {other_read}")
                            transactions[other]["status"] = "ABORTADA"
                            free_protected_vars(other)
                            break

        else:
            var_name = args[0]

            if cmd == "READ_POSSIBLE_VALUES":
                vals = []
                if var_name in global_db:
                    print(f"Agrega de global {global_db[var_name]}")
                    vals.append(global_db[var_name])
                
                for t in transactions:
                    print()
                    print(f"Revisando {t} de estado {transactions[t]['status']}")
                    if transactions[t]["status"] in ["ABIERTA", "EN_PREPARACION"]:
                        print(f"{t} en estado válido")
                        if var_name in transactions[t]["writes"]:
                            val = transactions[t]["writes"][var_name]
                            print(f"Ha escrito variable ({val})")
                            if val not in vals and val != "DELETE":
                                print(f"Agregando valor nuevo")
                                vals.append(transactions[t]["writes"][var_name])
                
                logs.append(json.dumps(vals))
                print(logs[-1])
            
            elif cmd == "READ_COMMIT":
                if var_name in global_db:
                    logs.append(global_db[var_name])
                else:
                    logs.append("NULL")
        
    # Generar archivo de logs
    output_file = open(f"logs/{filename}.txt", "w", encoding="utf-8")
    output_file.write("##LOGS##\n")
    if(len(logs) == 0):
        output_file.write("No hubo logs\n")
    else:
        for line in logs:
            output_file.write(f"{line}\n")
    output_file.write("##DATABASE##\n")
    if(len(global_db) == 0):
        output_file.write("No hay datos\n")
    else:
        for var in global_db:
            output_file.write(f"{var}={global_db[var]}\n")
    output_file.write("##STATS##\n")
    statuses = ["ABIERTA", "ABORTADA", "CONFIRMADA", "EN_PREPARACION", "INVALIDA"]

    for status in statuses:
        t_list = []
        for t in transactions:
            if transactions[t]["status"] == status:
                t_list.append(t)
        output_file.write(f"{status}={json.dumps(t_list)}\n")
    
    for t in transactions:
        if transactions[t]["status"] not in statuses:
            print(f"ERROR: {t} {transactions[t]['status']}")
    
    output_file.close()
            
                

