// Los registros reales están anonimizados (nombre 'ANONIMO', apellido = código). Solo cambia cómo se muestran.
const ANONIMO = 'ANONIMO'

export function etiquetaCodigo(codigo) {
  const m = /^(EST|EXT)-(\w+)$/.exec(codigo || '')
  if (!m) return codigo ? `Estudiante ${codigo}` : 'Estudiante'
  return m[1] === 'EXT' ? `Estudiante ext. ${m[2]}` : `Estudiante ${m[2]}`
}

export const esAnonimo = s => s?.nombre === ANONIMO

// "Apellido, Nombre" para registros con nombre; "Estudiante 0042" para anonimizados.
export function nombreEstudiante(s) {
  if (!s) return ''
  return esAnonimo(s) ? etiquetaCodigo(s.apellido) : `${s.apellido}, ${s.nombre}`
}

// Para textos ya armados como "Nombre Apellido" por el backend.
export function nombreCompleto(texto) {
  return texto?.startsWith(`${ANONIMO} `) ? etiquetaCodigo(texto.slice(ANONIMO.length + 1)) : texto
}
