package com.claude.cameo.bridge.util;

import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.openapi.uml.SessionManager;
import com.google.gson.JsonObject;
import javax.swing.SwingUtilities;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Marshals model operations to the correct thread context.
 * <p>
 * Read operations run on the calling thread (Cameo model reads are thread-safe).
 * Write operations are dispatched to the Swing EDT and wrapped in a SessionManager
 * session so that they participate in undo/redo and do not corrupt the model.
 */
public class EdtDispatcher {
    private static final Logger LOG = Logger.getLogger(EdtDispatcher.class.getName());
    private static final long TIMEOUT_SECONDS = 30;
    private static final Semaphore WRITE_PERMIT = new Semaphore(1);
    private static volatile String activeWriteName = null;
    private static volatile long activeWriteStartedAtMillis = 0L;

    /**
     * A model operation that receives the active Project and returns a result.
     */
    @FunctionalInterface
    public interface ModelAction<T> {
        T execute(Project project) throws Exception;
    }

    /**
     * Execute a read-only model action on the calling thread.
     *
     * @param action the action to execute
     * @param <T>    return type
     * @return the action result
     * @throws IllegalStateException if no project is open
     * @throws Exception             if the action throws
     */
    public static <T> T read(ModelAction<T> action) throws Exception {
        Project project = Application.getInstance().getProject();
        if (project == null) {
            throw new IllegalStateException("No project is open");
        }
        return action.execute(project);
    }

    /**
     * Execute a read-only action on the Swing EDT without creating a model session.
     * Use this for UI/presentation/export operations that require the EDT but should
     * not create undo history or dirty the model merely because evidence was read.
     */
    public static <T> T readOnEdt(String operationName, ModelAction<T> action, long timeoutSeconds) throws Exception {
        Project project = Application.getInstance().getProject();
        if (project == null) {
            throw new IllegalStateException("No project is open");
        }
        if (SwingUtilities.isEventDispatchThread()) {
            return action.execute(project);
        }

        CompletableFuture<T> future = new CompletableFuture<>();
        SwingUtilities.invokeLater(() -> {
            try {
                future.complete(action.execute(project));
            } catch (Exception e) {
                LOG.log(Level.SEVERE, "EDT read failed: " + operationName, e);
                future.completeExceptionally(e);
            }
        });

        try {
            return future.get(timeoutSeconds, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            throw new TimeoutException(
                    "Timed out waiting " + timeoutSeconds + "s for EDT read operation: " + operationName);
        }
    }

    /**
     * Execute a model-write action on the Swing EDT inside a SessionManager session.
     * <p>
     * The session is committed on success and cancelled on failure, ensuring
     * model integrity. The caller blocks (up to {@link #TIMEOUT_SECONDS} seconds)
     * until the EDT completes the work.
     *
     * @param sessionName human-readable session name (shown in undo history)
     * @param action      the write action to execute
     * @return the JsonObject result produced by the action
     * @throws IllegalStateException if no project is open
     * @throws Exception             if the action throws or the EDT times out
     */
    public static JsonObject write(String sessionName, ModelAction<JsonObject> action) throws Exception {
        return write(sessionName, action, TIMEOUT_SECONDS);
    }

    /**
     * Execute a model-write action with a caller-provided EDT timeout.
     *
     * @param sessionName    human-readable session name (shown in undo history)
     * @param action         the write action to execute
     * @param timeoutSeconds maximum time to wait for the EDT action
     * @return the JsonObject result produced by the action
     * @throws IllegalStateException if no project is open
     * @throws Exception             if the action throws or the EDT times out
     */
    public static JsonObject write(String sessionName, ModelAction<JsonObject> action, long timeoutSeconds)
            throws Exception {
        Project project = Application.getInstance().getProject();
        if (project == null) {
            throw new IllegalStateException("No project is open");
        }
        if (!WRITE_PERMIT.tryAcquire()) {
            throw new IllegalStateException("Another CATIA model write is already in progress"
                    + activeWriteDescription());
        }
        activeWriteName = sessionName;
        activeWriteStartedAtMillis = System.currentTimeMillis();

        CompletableFuture<JsonObject> future = new CompletableFuture<>();

        SwingUtilities.invokeLater(() -> {
            SessionManager sm = SessionManager.getInstance();
            boolean sessionCreated = false;
            try {
                if (sm.isSessionCreated(project)) {
                    throw new IllegalStateException("A CATIA model session is already open before starting "
                            + sessionName);
                }
                sm.createSession(project, sessionName);
                sessionCreated = true;
                JsonObject result = action.execute(project);
                sm.closeSession(project);
                sessionCreated = false;
                future.complete(result);
            } catch (Exception e) {
                if (sessionCreated) {
                    try {
                        sm.cancelSession(project);
                    } catch (Exception cancelEx) {
                        LOG.log(Level.WARNING,
                                "Failed to cancel session: " + sessionName, cancelEx);
                    }
                }
                LOG.log(Level.SEVERE, "Model write failed: " + sessionName, e);
                future.completeExceptionally(e);
            } finally {
                activeWriteName = null;
                activeWriteStartedAtMillis = 0L;
                WRITE_PERMIT.release();
            }
        });

        try {
            return future.get(timeoutSeconds, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            throw new TimeoutException("Timed out waiting " + timeoutSeconds + "s for CATIA model write: "
                    + sessionName + ". The EDT action may still be running; new writes are blocked until it finishes.");
        }
    }

    private static String activeWriteDescription() {
        String name = activeWriteName;
        if (name == null) {
            return "";
        }
        long elapsedMillis = Math.max(0L, System.currentTimeMillis() - activeWriteStartedAtMillis);
        return ": " + name + " has been running for " + elapsedMillis + "ms";
    }
}
