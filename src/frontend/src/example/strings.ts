/** Text that exists only in the example build, kept out of the shared strings on purpose. */
export const exampleEs = {
  banner: "Datos de ejemplo: nada de lo que ve es real y nada se guarda. Esto es una revisión del diseño.",
  footer: {
    designVersion: "Versión del diseño",
    contractVersion: "contrato",
    unreleased: "sin etiquetar",
  },
  panel: {
    summary: "Escenario de ejemplo",
    role: "Rol",
    roleAdministrator: "Administrador",
    roleGlobalManager: "Gerente global (solo consulta)",
    latency: "Retardo",
    failure: "Fallo simulado",
    failureNone: "Ninguno",
    failureNetwork: "Sin respuesta (red)",
    failureServer: "Error del servidor",
    failureStorage: "Almacenamiento rechaza el archivo",
    pendingBatch: "Empezar con un lote en revisión",
    emptyData: "Sin datos",
    matches: "Una fila coincide al confirmar",
    queue: "Cola de correo",
    queueRunning: "En curso",
    queueCompleted: "Lote completado con errores",
    queueGlovo: "Lote solo de Glovo",
    reset: "Restablecer el ejemplo",
  },
} as const;
