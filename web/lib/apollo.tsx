"use client";

import {
  ApolloClient,
  ApolloProvider,
  HttpLink,
  InMemoryCache,
  split,
} from "@apollo/client";
import { GraphQLWsLink } from "@apollo/client/link/subscriptions";
import { getMainDefinition } from "@apollo/client/utilities";
import { createClient } from "graphql-ws";

const API = "http://localhost:8000/graphql";
const WS = "ws://localhost:8000/graphql";

function makeClient() {
  const http = new HttpLink({ uri: API });
  const link =
    typeof window === "undefined"
      ? http
      : split(
          ({ query }) => {
            const def = getMainDefinition(query);
            return def.kind === "OperationDefinition" && def.operation === "subscription";
          },
          new GraphQLWsLink(createClient({ url: WS })),
          http,
        );
  return new ApolloClient({ link, cache: new InMemoryCache() });
}

export function GraphQLProvider({ children }: { children: React.ReactNode }) {
  return <ApolloProvider client={makeClient()}>{children}</ApolloProvider>;
}
