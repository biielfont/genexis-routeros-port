#!/bin/bash
# Compara los simbolos que necesitan los modulos de RouterOS con los que
# exporta el kernel compilado. Uso (dentro de WSL, como root):
#
#   bash tools/audit_symbols.sh
#
# Distingue tres cosas:
#   - simbolos que aporta otro modulo de RouterOS (no son problema)
#   - simbolos que el kernel ya tiene (aunque no los exporte, se ven aqui)
#   - simbolos que no estan en ninguna parte: el modulo no puede cargar
#
# No modifica nada; solo lee el rootfs, Module.symvers y System.map.
set -u

AQUI=$(cd "$(dirname "$0")/.." && pwd)
R=${ROS_ROOTFS:-$AQUI/ros/rootfs}
K=${KERNEL_TREE:-/opt/ros-port/linux-5.6.3}
NM=${CROSS_NM:-/opt/toolchain/bin/mips-buildroot-linux-gnu-nm}
SM=$K/System.map
SYMV=$K/Module.symvers

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

[ -d "$R" ] || { echo "FALTA rootfs: $R"; exit 1; }
if [ -s "$SYMV" ]; then
	# Lo que el cargador de modulos puede resolver es la tabla de
	# exportaciones (Module.symvers), no todos los simbolos de System.map.
	awk -F'\t' 'NF >= 2 {print $2}' "$SYMV" | sort -u > "$TMP/kern"
	FUENTE="Module.symvers"
else
	[ -s "$SM" ] || { echo "FALTA System.map: $SM"; exit 1; }
	awk '{print $3}' "$SM" | sort -u > "$TMP/kern"
	FUENTE="System.map"
fi

cd "$R" || exit 1

# Definidos por el conjunto de modulos (asi se resuelven las dependencias
# entre ellos, p.ej. switch.ko -> packet_hook.ko).
find . -name '*.ko' -print0 | xargs -0 "$NM" --defined-only 2>/dev/null \
	| awk 'NF>=3 {print $3}' | sort -u > "$TMP/def"

# Indefinidos de todos los modulos.
find . -name '*.ko' -print0 | xargs -0 "$NM" -u 2>/dev/null \
	| awk 'NF>=2 {print $2}' | sort -u > "$TMP/und"

# Los que deben venir del kernel (no los aporta ningun modulo).
comm -23 "$TMP/und" "$TMP/def" > "$TMP/solo_kernel"
# Y de esos, los que el kernel tampoco tiene.
comm -23 "$TMP/solo_kernel" "$TMP/kern" > "$TMP/faltan"

echo "modulos:        $(find . -name '*.ko' | wc -l)"
echo "simbolos def:   $(wc -l < "$TMP/def")"
echo "simbolos undef: $(wc -l < "$TMP/und")"
echo "solo kernel:    $(wc -l < "$TMP/solo_kernel")"
echo "exportados:     $(wc -l < "$TMP/kern") ($FUENTE)"
echo "FALTAN:         $(wc -l < "$TMP/faltan")"
echo

echo "--- simbolos que no estan ni en modulos ni en el kernel ---"
cat "$TMP/faltan"

echo
 echo "--- GPL-only importados por modulos sin licencia GPL ---"
if [ "$FUENTE" = "Module.symvers" ]; then
	awk -F'\t' '$4 == "EXPORT_SYMBOL_GPL" { print $2 }' "$SYMV" | sort -u > "$TMP/gpl"
	: > "$TMP/gpl_usados"
	while IFS= read -r ko; do
		lic=$(grep -am1 '^license=' "$ko" || true)
		case "$lic" in
			*GPL*) continue ;;
		esac
		"$NM" -u "$ko" 2>/dev/null | awk 'NF >= 2 { print $2 }' | sort -u > "$TMP/ko_und"
		comm -12 "$TMP/ko_und" "$TMP/gpl" | sed "s|^|  ${ko#./}: |" >> "$TMP/gpl_usados"
	done < <(find . -name '*.ko' -print)
	if [ -s "$TMP/gpl_usados" ]; then
		cat "$TMP/gpl_usados"
		echo "  (revisar: el kernel debe exportar sin GPL-only; ver parche_export_gpl)"
	else
		echo "  ninguno"
	fi
else
	echo "  (sin Module.symvers: no se puede comprobar)"
fi

