import React, { useState, useEffect } from "react";

import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import Button from "@mui/joy/Button";
import PropTypes from "prop-types";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import httpClient from "./httpClient";
import isUserAuthenticated from "./UserAuthentication";
import eventBus from "./EventBus";
import consoleLog from "./ConsoleLog";

function Row(props) {
  const { row: claim } = props;
  const { user } = props;
  const { deleted } = props;
  const [open, setOpen] = useState(false);
  const [deleteClaimStatus, setDeleteClaimStatus] = useState("Delete");

  const handleDeleteOnClick = () => {
    if (claim.name.includes(user.name) || user.admin) {
      if (deleteClaimStatus === "Deleting" || deleted) {
        return;
      }
      if (
        window.confirm(
          "\n\nAre you sure you want to delete claim " + claim.name + "?",
        )
      ) {
        httpClient.post(
          process.env.REACT_APP_API_URL +
            "/delete-claim?name=" +
            claim.name +
            "&user=" +
            user.name,
        );
        setDeleteClaimStatus("Deleting");
      }
    } else {
      alert("You can only delete your own claims");
    }
  };

  const handleOpenClusterInfoOnClick = () => {
    if (claim.name.includes(user.name) || user.admin) {
      setOpen(!open);
    } else {
      alert("You can only view your own claims");
    }
  };

  return (
    <React.Fragment>
      <TableRow
        key={claim.name}
        sx={{
          "&:last-child td, &:last-child th": { border: 0 },
        }}
      >
        <TableCell>
          <IconButton
            aria-label="expand row"
            size="small"
            onClick={handleOpenClusterInfoOnClick}
          >
            {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell component="th" scope="row">
          {claim.name}
        </TableCell>
        <TableCell align="center">{claim.pool}</TableCell>
        <TableCell align="center">{claim.namespace}</TableCell>
        <TableCell align="center">{claim.created_at}</TableCell>

        <TableCell align="center">
          <Button
            variant="plain"
            loading={deleted || deleteClaimStatus === "Deleting"}
            color="danger"
            onClick={handleDeleteOnClick}
          >
            DELETE
          </Button>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 1 }}>
              <Typography
                variant="h6"
                gutterBottom
                component="div"
              ></Typography>
              <Table size="small" aria-label="claimInfo">
                <TableHead>
                  <TableRow>
                    <TableCell align="center"></TableCell>
                    <TableCell align="center"></TableCell>
                    <TableCell align="center"></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {claim.info.map((info) => (
                    <TableRow key={info.name}>
                      <TableCell>
                        <Button
                          variant="plain"
                          component="a"
                          disabled={info.login_cmd === "Not Ready"}
                          href={info.console}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          CONSOLE
                        </Button>
                      </TableCell>
                      <TableCell align="center">
                        <p>
                          {info.creds.split("#")[0] +
                            " / " +
                            info.creds.split("#")[1]}
                        </p>
                        <Button
                          variant="plain"
                          disabled={info.login_cmd === "Not Ready"}
                          onClick={() => {
                            navigator.clipboard.writeText(info.login_cmd);
                          }}
                        >
                          COPY LOGIN COMMAND
                        </Button>
                      </TableCell>
                      <TableCell align="center">
                        <Button
                          variant="plain"
                          component="a"
                          disabled={info.login_cmd === "Not Ready"}
                          href={process.env.REACT_APP_API_URL + info.kubeconfig}
                        >
                          KUBECONFIG
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </React.Fragment>
  );
}

Row.propTypes = {
  user: PropTypes.shape({
    name: PropTypes.string.isRequired,
  }),
  row: PropTypes.shape({
    deleted: PropTypes.bool,
    name: PropTypes.string.isRequired,
    pool: PropTypes.string.isRequired,
    namespace: PropTypes.string.isRequired,
    info: PropTypes.arrayOf(
      PropTypes.shape({
        console: PropTypes.string.isRequired,
        creds: PropTypes.string.isRequired,
        kubeconfig: PropTypes.string.isRequired,
      }),
    ).isRequired,
  }).isRequired,
};

function ClusterClaims() {
  const [user, setUser] = useState(null);
  const [clusterClaims, setClusterClaims] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deletedClaims, setDeletedClaims] = useState([]);

  const getUser = async () => {
    const user = await isUserAuthenticated();
    setUser(user);
  };

  const getClusterClaims = async (loading) => {
    try {
      if (loading) {
        setLoading(true);
      }
      consoleLog("fetching cluster claims");

      const res = await fetch(
        process.env.REACT_APP_API_URL + "/cluster-claims",
      );
      const data = await res.json();
      setClusterClaims(data);
      if (loading) {
        setLoading(false);
      }
    } catch (error) {
      console.error(error);
      if (loading) {
        setLoading(false);
      }
    }
  };

  const processClaimDone = async () => {
    eventBus.on("claimDone", (_) => {
      getClusterClaims();
    });
  };

  const processDeletedAllClaimsDone = async () => {
    eventBus.on("deleteAllDone", (_) => {
      getDeletedClaims();
    });
  };

  const getDeletedClaims = async () => {
    try {
      const res = await fetch(
        process.env.REACT_APP_API_URL + "/claims-delete-in-progress-endpoint",
      );
      const data = await res.json();
      setDeletedClaims(data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    getDeletedClaims();
    processClaimDone();
    processDeletedAllClaimsDone();
    getClusterClaims(true);
    getUser();
    const clusterClaimsInterval = setInterval(() => {
      getClusterClaims();
    }, 30 * 1000);
    const deletedClaimsInterval = setInterval(() => {
      getDeletedClaims();
    }, 1 * 1000);
    return () => clearInterval(clusterClaimsInterval, deletedClaimsInterval);
  }, []);

  return (
    <div>
      <h3>Active Claims</h3>
      {loading ? (
        <Box sx={{ display: "flex" }}>
          <CircularProgress size={30} />
        </Box>
      ) : (
        <>
          <TableContainer component={Paper}>
            <Table aria-label="collapsible table">
              <TableHead>
                <TableRow>
                  <TableCell></TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell align="center">Pool</TableCell>
                  <TableCell align="center">Namespace</TableCell>
                  <TableCell align="center">Created At (UTC)</TableCell>
                  <TableCell align="center"></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {clusterClaims
                  .map((claim) => claim)
                  .sort((a, b) => (a.name > b.name ? 1 : -1))
                  .map((claim) => (
                    <Row
                      key={claim.name}
                      row={claim}
                      user={user}
                      deleted={deletedClaims.includes(claim.name)}
                    />
                  ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </div>
  );
}

export default ClusterClaims;
