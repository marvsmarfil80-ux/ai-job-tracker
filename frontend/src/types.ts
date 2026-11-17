export type ValidationItem = {
  loc: (string | number)[]
  msg: string
  type: string
}

export class ApiError extends Error {
  status: number
  detail: string
  validation: ValidationItem[] | null

  constructor(status: number, detail: string, validation: ValidationItem[] | null = null) {
    super(detail)
    this.status = status
    this.detail = detail
    this.validation = validation
  }
}