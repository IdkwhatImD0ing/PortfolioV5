"use client";

import type { AreaId } from "@/lib/sect/areas";
import type { BodyProps } from "../ui";
import { AbodeBody, SummitBody } from "./abode";
import { ForgeBody } from "./forge";
import { GateBody, MirrorBody } from "./intro";
import { ArenaBody, LibraryBody, MissionBody } from "./records";
import { ScrollBody } from "./scroll";
import { FormationBody, StelesBody } from "./systems";

const BODIES: Record<AreaId, (props: BodyProps) => React.JSX.Element> = {
  gate: GateBody,
  mirror: MirrorBody,
  forge: ForgeBody,
  arena: ArenaBody,
  mission: MissionBody,
  library: LibraryBody,
  steles: StelesBody,
  scroll: ScrollBody,
  formation: FormationBody,
  abode: AbodeBody,
  summit: SummitBody,
};

/** The complete content of one main-page section, as it reads in the sect. */
export function AreaBody({ area, ...props }: BodyProps & { area: AreaId }) {
  const Body = BODIES[area];
  return <Body {...props} />;
}
