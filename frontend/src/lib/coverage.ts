/** Which keywords a resume contains, as the API calculated them. `ratio` is 0 to 1. */
export interface Coverage {
  covered: string[]
  missing: string[]
  ratio: number
}

/** Coverage of a tailored resume (GET /applications/{id}/coverage?resume_id=): how it compares
 * with the base resume, worked out by the API. */
export interface ResumeCoverage extends Coverage {
  base: Coverage
  newly_covered: string[]
  still_missing: string[]
}
