/** Which keywords a resume contains, as the API calculated them. `ratio` is 0 to 1. */
export interface Coverage {
  covered: string[]
  missing: string[]
  ratio: number
}
